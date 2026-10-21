import { FFmpeg, CommandResult } from '@samprojects/hmos-ffmpeg';
import { common } from '@kit.AbilityKit';
import { fileIo as fs } from '@kit.CoreFileKit';

@Entry
@Component
struct Index {
  @State message: string = '正在加载 HAR…';
  @State version: string = '';
  @State status: string = '准备中';
  @State available: boolean = false;
  @State running: boolean = false;
  @State completed: number = 0;
  private activeId: number = -1;

  aboutToAppear(): void {
    try {
      const info = FFmpeg.getBuildInfo();
      this.version = 'FFmpeg ' + info.version;
      this.available = info.commandExecution === 'experimental-serial';
      this.status = this.available ? '准备就绪' : '命令引擎未启用';
      this.message = this.available ? 'HAR 已加载。点击“一键自检”开始，无需选择文件或联网。'
        : '当前 HAR 不包含实验命令引擎，请确认导入的是 command-test 版本。';
    } catch (e) { this.status = '加载失败'; this.message = String(e); }
  }

  aboutToDisappear(): void {
    if (this.activeId >= 0) FFmpeg.cancel(this.activeId);
  }

  private pass(label: string): void {
    this.completed++;
    this.message += '\n通过 · ' + label;
    console.info('FFmpegTest: PASS ' + label);
  }

  private async runCommand(args: string[], timeoutSeconds: number = 30): Promise<CommandResult> {
    const task = FFmpeg.execute(args, timeoutSeconds);
    this.activeId = task.id;
    try { return await task.result; }
    finally { this.activeId = -1; }
  }

  private async verifyAudio(path: string): Promise<void> {
    const info = await FFmpeg.probe(path);
    if (fs.statSync(path).size <= 44 || info.durationUs <= 0 || info.streams.length === 0 ||
      info.streams[0].codec !== 'pcm_s16le' || info.streams[0].sampleRate !== 48000) {
      throw new Error('输出音频校验失败：' + path);
    }
  }

  private async testCommands(): Promise<void> {
    this.running = true;
    this.completed = 0;
    this.status = '正在自检';
    this.message = '使用内置的 0.2 秒音频测试命令执行。\n非法参数测试预期返回错误，不是应用故障。';
    try {
      const context = this.getUIContext().getHostContext() as common.UIAbilityContext;
      const input = context.filesDir + '/command-input.wav';
      const output = context.filesDir + '/command-output.wav';
      const filtered = context.filesDir + '/command-filtered.wav';
      const data = await context.resourceManager.getRawFileContent('command-input.wav');
      const file = fs.openSync(input, fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
      try {
        const written = fs.writeSync(file.fd, data.buffer, { offset: data.byteOffset, length: data.byteLength });
        if (written !== data.byteLength) throw new Error('内置音频写入不完整');
      } finally { fs.closeSync(file); }

      const labels: string[] = ['版本查询', '非法参数正确返回错误', '错误后重试', '重封装及输出校验', '音量滤镜及输出校验'];
      const commands: string[][] = [
        ['-version'],
        ['-not_an_ffmpeg_option'],
        ['-version'],
        ['-y', '-i', input, '-c:a', 'copy', output],
        ['-y', '-i', input, '-filter_complex', '[0:a]volume=0.5[a]', '-map', '[a]', '-c:a', 'pcm_s16le', filtered]
      ];
      for (let i = 0; i < commands.length; ++i) {
        const result = await this.runCommand(commands[i]);
        if ((result.exitCode !== 0) !== (i === 1) || result.cancelled || result.timedOut) {
          throw new Error(labels[i] + '失败，exitCode=' + result.exitCode + '\n' + result.logs);
        }
        if (i === 0 && !result.logs.includes('9.0.2')) throw new Error('版本返回不符合预期');
        if (i === 3) await this.verifyAudio(output);
        if (i === 4) await this.verifyAudio(filtered);
        this.pass(labels[i]);
      }

      const task = FFmpeg.execute(['-y', '-stream_loop', '-1', '-re', '-i', input,
        '-t', '60', '-c:a', 'copy', context.filesDir + '/command-cancel.wav'], 30);
      this.activeId = task.id;
      const timer = setTimeout((): void => { FFmpeg.cancel(task.id); }, 500);
      let cancelled: CommandResult;
      try { cancelled = await task.result; }
      finally { clearTimeout(timer); this.activeId = -1; }
      if (!cancelled.cancelled || cancelled.exitCode === 0) throw new Error('取消失败');
      this.pass('取消任务');
      const retry = await this.runCommand(['-version']);
      if (retry.exitCode !== 0 || retry.cancelled || retry.timedOut) throw new Error('取消后重试失败');
      this.pass('取消后重试');

      const timeout = await this.runCommand(['-y', '-stream_loop', '-1', '-re', '-i', input,
        '-t', '60', '-c:a', 'copy', context.filesDir + '/command-timeout.wav'], 1);
      if (!timeout.timedOut || timeout.exitCode === 0) throw new Error('超时退出失败');
      this.pass('超时退出');
      const recovered = await this.runCommand(['-version']);
      if (recovered.exitCode !== 0 || recovered.cancelled || recovered.timedOut) throw new Error('超时后重试失败');
      this.pass('超时后重试');

      this.status = '全部通过 · 9 / 9';
      this.message += '\n\n当前模拟器已通过上述命令测试。可再次点击自检验证重复调用。';
    } catch (e) {
      this.status = '未通过 · ' + this.completed + ' / 9';
      this.message += '\n\n测试停止：' + String(e);
      console.error('FFmpegTest: ' + String(e));
    } finally { this.running = false; }
  }

  build() {
    Column({ space: 12 }) {
      Text('FFmpeg 命令测试').fontSize(24).fontWeight(FontWeight.Bold)
      Text(this.version).fontSize(14).fontColor('#52606D')
      Text(this.status).fontSize(18).fontColor(this.completed === 9 ? '#087F5B' : '#263238')
      Progress({ value: this.completed, total: 9, type: ProgressType.Linear }).width('100%')
      Button(this.running ? '自检中…' : '一键自检').width('100%')
        .enabled(this.available && !this.running).onClick((): void => { this.testCommands(); })
      Button('取消当前任务').width('100%').enabled(this.running).onClick((): void => {
        if (this.activeId >= 0) FFmpeg.cancel(this.activeId);
      })
      Scroll() {
        Text(this.message).width('100%').fontSize(14).textAlign(TextAlign.Start)
          .copyOption(CopyOptions.LocalDevice).padding(12)
      }.layoutWeight(1).width('100%').backgroundColor('#F2F5F7').borderRadius(12)
      Text('仅供测试 · 不执行 shell · 可长按复制结果').fontSize(12).fontColor('#667788')
    }.padding({ top: 24, bottom: 24, left: 20, right: 20 }).width('100%').height('100%')
  }
}
