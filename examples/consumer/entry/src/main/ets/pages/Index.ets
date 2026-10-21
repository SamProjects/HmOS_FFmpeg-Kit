import { FFmpeg, CommandResult } from '@samprojects/hmos-ffmpeg';
import { common } from '@kit.AbilityKit';
import { fileIo as fs } from '@kit.CoreFileKit';

@Entry
@Component
struct Index {
  @State message: string = 'Loading FFmpeg';
  @State available: boolean = false;
  @State running: boolean = false;
  private activeId: number = -1;

  aboutToAppear(): void {
    try {
      const info = FFmpeg.getBuildInfo();
      this.message = JSON.stringify(info);
      this.available = info.commandExecution === 'experimental-serial';
    } catch (e) { this.message = String(e); }
  }

  private async runCommand(args: string[]): Promise<CommandResult> {
    const task = FFmpeg.execute(args, 30);
    this.activeId = task.id;
    try { return await task.result; }
    finally { this.activeId = -1; }
  }

  private async testCommands(): Promise<void> {
    this.running = true;
    this.message = '开始手机端命令测试（未执行 shell）';
    try {
      const context = getContext(this) as common.UIAbilityContext;
      const input = context.filesDir + '/command-input.wav';
      const output = context.filesDir + '/command-output.wav';
      const filtered = context.filesDir + '/command-filtered.wav';
      const data = await context.resourceManager.getRawFileContent('command-input.wav');
      const file = fs.openSync(input, fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
      try { fs.writeSync(file.fd, data.buffer, { offset: data.byteOffset, length: data.byteLength }); }
      finally { fs.closeSync(file); }
      const commands: string[][] = [
        ['-version'],
        ['-not_an_ffmpeg_option'],
        ['-version'],
        ['-y', '-i', input, '-c:a', 'copy', output],
        ['-y', '-i', input, '-filter_complex', '[0:a]volume=0.5[a]', '-map', '[a]', '-c:a', 'pcm_s16le', filtered]
      ];
      for (let i = 0; i < commands.length; ++i) {
        const result = await this.runCommand(commands[i]);
        this.message += '\n测试 ' + (i + 1) + '：exitCode=' + result.exitCode;
        if ((result.exitCode !== 0) !== (i === 1)) {
          throw new Error('返回码不符合预期：' + result.logs);
        }
      }
      const task = FFmpeg.execute(['-y', '-stream_loop', '-1', '-re', '-i', input,
        '-t', '60', '-c:a', 'copy', context.filesDir + '/command-cancel.wav'], 30);
      this.activeId = task.id;
      const timer = setTimeout((): void => { FFmpeg.cancel(task.id); }, 500);
      let cancelled: CommandResult;
      try { cancelled = await task.result; }
      finally { clearTimeout(timer); this.activeId = -1; }
      if (!cancelled.cancelled || cancelled.exitCode === 0) throw new Error('取消失败');
      this.message += '\n取消测试通过';
      const retry = await this.runCommand(['-version']);
      if (retry.exitCode !== 0) throw new Error('取消后重试失败');
      this.message += '\n取消后重试通过\n请同时检查输出 WAV 能否播放：' + output;
    } catch (e) { this.message += '\n测试失败：' + String(e); }
    finally { this.running = false; }
  }

  build() {
    Column() {
      if (this.available) {
        Button('运行命令测试').enabled(!this.running).onClick((): void => { this.testCommands(); })
        Button('取消当前任务').enabled(this.running).onClick((): void => {
          if (this.activeId >= 0) FFmpeg.cancel(this.activeId);
        })
      }
      Scroll() { Text(this.message).padding(24) }.layoutWeight(1)
    }.width('100%').height('100%')
  }
}
