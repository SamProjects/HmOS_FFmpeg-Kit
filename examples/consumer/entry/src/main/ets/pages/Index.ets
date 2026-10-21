import { FFmpeg, CommandResult, MediaInfo } from '@samprojects/hmos-ffmpeg';
import { common } from '@kit.AbilityKit';
import { fileIo as fs } from '@kit.CoreFileKit';
import { util } from '@kit.ArkTS';

interface TestCase {
  id: string; label: string; args: string[]; output: string; expected: string;
  timeout: number; cancelMs: number; repeatCancel: boolean; concurrent: boolean;
  requireLive: boolean; requireProgress: boolean; requireTruncated: boolean;
  videoCodec: string; audioCodec: string; width: number; height: number;
  sampleRate: number; channels: number; minDuration: number; maxDuration: number; verifyDecode: boolean;
}
interface TestRecord {
  id: string; label: string; state: string; detail: string; args: string[];
  exitCode: number; cancelled: boolean; timedOut: boolean; elapsedMs: number;
  liveReads: number; liveUpdates: number; progressUs: number; logsTruncated: boolean;
}

@Entry
@Component
struct Index {
  @State message: string = '正在加载 HAR…';
  @State logs: string = '';
  @State version: string = '';
  @State catalog: string = '';
  @State status: string = '准备中';
  @State current: string = '';
  @State available: boolean = false;
  @State running: boolean = false;
  @State completed: number = 0;
  @State total: number = 97;
  @State passed: number = 0;
  @State failed: number = 0;
  @State unsupported: number = 0;
  @State mediaSeconds: string = '0.00';
  @State showLogs: boolean = true;
  private activeId: number = -1;
  private stopRequested: boolean = false;
  private report: TestRecord[] = [];
  private logScroller: Scroller = new Scroller();

  aboutToAppear(): void {
    try {
      const info = FFmpeg.getBuildInfo();
      this.version = 'FFmpeg ' + info.version + ' · 扩展编解码测试 v3';
      const caps = FFmpeg.getCapabilities();
      this.catalog = info.license + ' · 编码器 ' + caps.encoders.length + ' · 解码器 ' + caps.decoders.length;
      this.available = info.commandExecution === 'experimental-serial';
      this.status = this.available ? '准备就绪' : '命令引擎未启用';
      this.message = '内置原始 AV1 视频和由它生成的 8 秒 MPEG4 测试片段。\n' +
        '已加入 AV1 软件解码及更多视频、音频编码器，完整测试需数分钟。\n' +
        '预期错误、取消及超时也属于测试，不代表 App 故障。';
    } catch (e) { this.status = '加载失败'; this.message = String(e); }
  }
  aboutToDisappear(): void {
    this.stopRequested = true;
    if (this.activeId >= 0) FFmpeg.cancel(this.activeId);
  }
  private context(): common.UIAbilityContext {
    return this.getUIContext().getHostContext() as common.UIAbilityContext;
  }
  private write(path: string, data: ArrayBuffer): void {
    const file = fs.openSync(path, fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
    try {
      if (data.byteLength > 0 && fs.writeSync(file.fd, data) !== data.byteLength) throw new Error('文件写入不完整：' + path);
    } finally { fs.closeSync(file); }
  }
  private writeText(path: string, text: string): void {
    // HarmonyOS TextEncoder.encodeInto('') may return undefined. Create a real empty file.
    if (text.length === 0) { this.write(path, new ArrayBuffer(0)); return; }
    const bytes = new util.TextEncoder().encodeInto(text);
    this.write(path, bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
  }
  private async fixture(name: string): Promise<void> {
    const bytes = await this.context().resourceManager.getRawFileContent(name);
    this.write(this.context().filesDir + '/' + name,
      bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
  }
  private resolve(value: string): string {
    const dir = this.context().filesDir;
    return value.replace(/\{ORIGINAL\}/g, dir + '/user-video.mp4')
      .replace(/\{VIDEO\}/g, dir + '/compatible-video.mp4').replace(/\{DIR\}/g, dir);
  }
  private check(condition: boolean, message: string): void {
    if (!condition) throw new Error(message);
  }
  private displayLogs(value: string): void {
    this.logs = value.slice(-18000);
    if (this.showLogs) this.logScroller.scrollEdge(Edge.Bottom);
  }
  private async verifyOutput(c: TestCase): Promise<void> {
    if (!c.output) return;
    const path = this.resolve(c.output);
    this.check(fs.statSync(path).size > 0, '输出为空');
    const info: MediaInfo = await FFmpeg.probe(path);
    if (c.minDuration > 0) this.check(info.durationUs >= c.minDuration * 1000000, '输出时长过短');
    if (c.maxDuration > 0) this.check(info.durationUs <= c.maxDuration * 1000000, '输出时长过长');
    if (c.videoCodec) {
      const video = info.streams.find(s => s.type === 'video');
      this.check(video !== undefined && video.codec === c.videoCodec, '视频编码不符合预期');
      if (video && c.width) this.check(video.width === c.width && video.height === c.height, '视频尺寸不符合预期');
    }
    if (c.audioCodec) {
      const audio = info.streams.find(s => s.type === 'audio');
      this.check(audio !== undefined && audio.codec === c.audioCodec, '音频编码不符合预期');
      if (audio && c.sampleRate) this.check(audio.sampleRate === c.sampleRate, '采样率不符合预期');
      if (audio && c.channels) this.check(audio.channels === c.channels, '声道数不符合预期');
    }
    if (c.label === '视频去音轨') this.check(!info.streams.some(s => s.type === 'audio'), '音轨未移除');
    if (c.verifyDecode) {
      const task = FFmpeg.execute(['-v', 'error', '-xerror', '-i', path, '-f', 'null', this.context().filesDir + '/verify.null']);
      this.activeId = task.id;
      try { const decoded = await task.result; this.check(decoded.exitCode === 0, '输出无法完整解码：' + decoded.logs); }
      finally { this.activeId = -1; }
    }
  }
  private async executeCase(c: TestCase): Promise<void> {
    const start = Date.now();
    const args = c.args.map(value => this.resolve(value));
    const record: TestRecord = { id: c.id, label: c.label, state: '失败', detail: '', args: args,
      exitCode: -999, cancelled: false, timedOut: false, elapsedMs: 0,
      liveReads: 0, liveUpdates: 0, progressUs: 0, logsTruncated: false };
    this.current = c.id + ' · ' + c.label;
    this.mediaSeconds = '0.00';
    this.logs = '$ ffmpeg ' + args.join(' ') + '\n';
    let poll: number = -1;
    let cancelTimer: number = -1;
    let lastLogs: string = '';
    let commandResult: CommandResult | undefined = undefined;
    let rejected: boolean = false;
    let concurrentBlocked: boolean = !c.concurrent;
    try {
      try {
        const task = FFmpeg.execute(args, c.timeout);
        this.activeId = task.id;
        poll = setInterval((): void => {
          const snapshot = FFmpeg.readCommandLogs(task.id);
          if (snapshot) {
            record.liveReads++;
            if (snapshot.logs !== lastLogs) { record.liveUpdates++; lastLogs = snapshot.logs; }
            this.displayLogs('$ ffmpeg ' + args.join(' ') + '\n' + snapshot.logs);
            const progress = FFmpeg.progressUs(task.id);
            record.progressUs = Math.max(record.progressUs, progress);
            this.mediaSeconds = (record.progressUs / 1000000).toFixed(2);
          }
        }, 150);
        if (c.cancelMs >= 0) {
          cancelTimer = setTimeout((): void => {
            FFmpeg.cancel(task.id);
            if (c.repeatCancel) { FFmpeg.cancel(task.id); FFmpeg.cancel(task.id); }
          }, c.cancelMs);
        }
        if (c.concurrent) {
          concurrentBlocked = false;
          try { await FFmpeg.execute(['-version']).result; } catch (e) {
            concurrentBlocked = String(e).includes('exclusive');
          }
          // Await the original command even if concurrency protection fails.
        }
        commandResult = await task.result;
        this.check(concurrentBlocked, '并发调用未被正确拒绝');
        this.check(FFmpeg.readCommandLogs(task.id) === null && FFmpeg.progressUs(task.id) === -1,
          '已完成任务未清理');
        FFmpeg.cancel(task.id); // Cancelling an already finished id must be harmless.
      } catch (e) {
        if (c.expected === 'reject' && String(e).includes('disabled in this test API')) rejected = true;
        else throw new Error(String(e));
      } finally {
        if (poll >= 0) clearInterval(poll);
        if (cancelTimer >= 0) clearTimeout(cancelTimer);
        this.activeId = -1;
      }
      if (commandResult) {
        const result = commandResult;
        record.exitCode = result.exitCode; record.cancelled = result.cancelled;
        record.timedOut = result.timedOut; record.logsTruncated = result.logsTruncated;
        this.displayLogs('$ ffmpeg ' + args.join(' ') + '\n' + result.logs);
        const logPath = this.context().filesDir + '/test-' + c.id + '.log';
        this.writeText(logPath, result.logs);
        if (c.label === '静默日志级别') {
          this.check(result.logs.length === 0 && fs.statSync(logPath).size === 0, '静默命令未正确保存空日志');
        }
        if (c.expected === 'cancel') {
          this.check(result.cancelled && result.exitCode !== 0 && !result.timedOut, '未正确取消');
          this.check(Date.now() - start - c.cancelMs < 5000, '取消响应超过 5 秒');
        } else if (c.expected === 'timeout') {
          this.check(result.timedOut && !result.cancelled && result.exitCode !== 0, '未正确超时');
          this.check(Date.now() - start < 6000, '超时退出过慢');
        } else if (c.expected === 'error') {
          this.check(result.exitCode !== 0 && !result.cancelled && !result.timedOut && result.logs.length > 0, '未正确返回错误日志');
        } else if (c.expected === 'capability' && result.exitCode !== 0) {
          this.check(!result.cancelled && !result.timedOut &&
            (result.logs.includes('hardware accelerated AV1') || result.logs.includes('Function not implemented') ||
            result.logs.includes('Decoder (codec av1) not found')), '能力检测遇到非预期错误');
          record.state = '不支持'; record.detail = '当前 HAR 无可用 AV1 解码后端，原始日志已保存';
        } else {
          this.check(result.exitCode === 0 && !result.cancelled && !result.timedOut, '命令失败，exitCode=' + result.exitCode);
          if (c.label.includes('版本') || c.args[0] === '-version') this.check(result.logs.includes('9.0.2'), '版本日志缺失');
          if (c.args[0] === '-L') this.check(result.logs.includes('Lesser General Public License') && result.logs.includes('version 3'), '运行时许可不是 LGPLv3');
          if (c.requireLive) this.check(record.liveReads > 1 && record.liveUpdates > 1 && result.logs.includes('frame='), '执行期间未读到实时日志');
          if (c.requireProgress) this.check(record.progressUs > 0, '执行期间未读到进度');
          if (c.requireTruncated) this.check(result.logsTruncated && result.logs.length > 100000, '日志截断上限未生效');
          await this.verifyOutput(c);
        }
      } else this.check(rejected, '命令没有返回结果');
      if (record.state !== '不支持') record.state = '通过';
    } catch (e) { record.detail = String(e); }
    record.elapsedMs = Date.now() - start;
    this.report.push(record);
    this.completed++;
    if (record.state === '通过') this.passed++;
    else if (record.state === '不支持') this.unsupported++;
    else this.failed++;
    this.message += '\n' + record.state + ' · ' + c.id + ' ' + c.label +
      ' (' + record.elapsedMs + 'ms)' + (record.detail ? '\n' + record.detail : '');
    console.info('FFmpegTest: ' + JSON.stringify(record));
    this.writeText(this.context().filesDir + '/test-report.json', JSON.stringify(this.report, null, 2));
  }
  private async testCommands(): Promise<void> {
    this.running = true; this.stopRequested = false; this.report = [];
    this.completed = 0; this.passed = 0; this.failed = 0; this.unsupported = 0;
    this.status = '正在准备素材'; this.message = '执行全部测试；单项失败后继续。';
    try {
      await this.fixture('user-video.mp4'); await this.fixture('compatible-video.mp4');
      const data = await this.context().resourceManager.getRawFileContent('command-cases.json');
      const cases = JSON.parse(util.TextDecoder.create('utf-8').decodeWithStream(data)) as TestCase[];
      this.total = cases.length;
      for (const c of cases) {
        if (this.stopRequested) break;
        this.status = '测试中 · ' + (this.completed + 1) + '/' + this.total;
        await this.executeCase(c);
      }
      this.status = (this.stopRequested ? '已停止' : '测试完成') + ' · 通过 ' + this.passed +
        ' / 失败 ' + this.failed + ' / 不支持 ' + this.unsupported;
      this.message += '\n\n报告目录：' + this.context().filesDir + '\n再次测试可验证状态复位。';
    } catch (e) { this.status = '测试准备失败'; this.message += '\n' + String(e); }
    finally { this.running = false; this.current = ''; }
  }
  private async manualCancel(): Promise<void> {
    this.running = true; this.stopRequested = false; this.status = '手动中断演示';
    this.message = '正在按实时速度处理视频，请点击“取消当前任务”；也可点击“停止全部”。';
    try {
      await this.fixture('compatible-video.mp4');
      if (this.stopRequested) { this.status = '已停止'; return; }
      const task = FFmpeg.execute(['-y', '-loglevel', 'verbose', '-stats', '-stats_period', '0.2', '-re', '-stream_loop', '-1', '-i',
        this.context().filesDir + '/compatible-video.mp4', '-t', '60', '-c:v', 'mpeg4', '-c:a', 'aac',
        this.context().filesDir + '/manual-cancel.mp4'], 90);
      this.activeId = task.id;
      const timer = setInterval((): void => {
        const value = FFmpeg.readCommandLogs(task.id);
        if (value) this.displayLogs(value.logs);
        this.mediaSeconds = (Math.max(0, FFmpeg.progressUs(task.id)) / 1000000).toFixed(2);
      }, 150);
      try {
        const result = await task.result;
        this.displayLogs(result.logs);
        this.status = result.cancelled ? '手动取消成功，可立即重新测试' : '命令已结束 · ' + result.exitCode;
        this.message += '\n' + JSON.stringify(result).slice(0, 350);
      } finally { clearInterval(timer); this.activeId = -1; }
    } catch (e) { this.status = '演示失败'; this.message += '\n' + String(e); }
    finally { this.running = false; }
  }
  build() {
    Column({ space: 8 }) {
      Text('FFmpeg 视频与中断测试').fontSize(22).fontWeight(FontWeight.Bold)
      Text(this.version).fontSize(12).fontColor('#52606D')
      Text(this.catalog).fontSize(10).fontColor('#52606D')
      Text(this.status).fontSize(14).fontColor(this.failed > 0 ? '#B42318' : '#087F5B')
      Progress({ value: this.completed, total: this.total, type: ProgressType.Linear }).width('100%')
      Button(this.running ? '测试中…' : '运行全部 ' + this.total + ' 项测试').width('100%')
        .enabled(this.available && !this.running).onClick((): void => { this.testCommands(); })
      Row({ space: 8 }) {
        Button('手动中断演示').layoutWeight(1).fontSize(14).enabled(this.available && !this.running)
          .onClick((): void => { this.manualCancel(); })
        Button('取消当前任务').layoutWeight(1).fontSize(14).enabled(this.running)
          .onClick((): void => { if (this.activeId >= 0) FFmpeg.cancel(this.activeId); })
        Button('停止全部').layoutWeight(1).fontSize(14).enabled(this.running)
          .onClick((): void => { this.stopRequested = true; if (this.activeId >= 0) FFmpeg.cancel(this.activeId); })
      }.width('100%')
      Text(this.current + ' · 已处理 ' + this.mediaSeconds + ' 秒').fontSize(12).maxLines(2)
      Row({ space: 8 }) {
        Button(this.showLogs ? '显示测试结果' : '显示实时日志').fontSize(13)
          .onClick((): void => { this.showLogs = !this.showLogs; })
        Text('可长按复制 · 单项日志最多 256 KiB').fontSize(11).fontColor('#667788')
      }
      if (this.showLogs) {
        Scroll(this.logScroller) {
          Text(this.logs).width('100%').fontSize(12).fontFamily('monospace').fontColor('#D8E8DE')
            .copyOption(CopyOptions.LocalDevice).padding(10)
        }.layoutWeight(1).width('100%').backgroundColor('#15251D').borderRadius(10)
      } else {
        Scroll() {
          Text(this.message).width('100%').fontSize(13).copyOption(CopyOptions.LocalDevice).padding(10)
        }.layoutWeight(1).width('100%').backgroundColor('#F2F5F7').borderRadius(10)
      }
      Text('AV1 软件解码 · 多视频/音频编码器 · 全程离线').fontSize(10).fontColor('#667788')
    }.padding({ top: 20, bottom: 16, left: 16, right: 16 }).width('100%').height('100%')
  }
}
