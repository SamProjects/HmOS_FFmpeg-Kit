import native from 'libhmosffmpeg.so';

export interface BuildInfo { version: string; license: string; configuration: string; hardwareBackend: string; commandExecution: string; }
export interface Capabilities {
  encoders: string[]; decoders: string[]; filters: string[];
  muxers: string[]; demuxers: string[]; inputProtocols: string[]; outputProtocols: string[];
}
export interface StreamInfo { index: number; codec: string; type: string; width: number; height: number; sampleRate: number; channels: number; }
export interface MediaInfo { format: string; durationUs: number; streams: StreamInfo[]; }
export interface TranscodeOptions {
  input: string;
  output: string;
  videoCodec?: string;
  audioCodec?: string;
  videoFilter?: string;
  audioFilter?: string;
  caFile?: string;
}
export interface CommandResult { exitCode: number; cancelled: boolean; timedOut: boolean; logs: string; logsTruncated: boolean; }
export interface CommandLogSnapshot { logs: string; logsTruncated: boolean; }
export interface CommandSession { id: number; result: Promise<CommandResult>; }
export interface Session { id: number; result: Promise<void>; }

export class FFmpeg {
  private static sequence: number = 0;
  static getBuildInfo(): BuildInfo { return JSON.parse(native.getBuildInfo()) as BuildInfo; }
  static getCapabilities(): Capabilities { return JSON.parse(native.getCapabilities()) as Capabilities; }
  static async probe(input: string, caFile: string = ''): Promise<MediaInfo> {
    const value = await native.run(++FFmpeg.sequence, 'probe', input, '', '', '', '', '', caFile);
    return JSON.parse(value) as MediaInfo;
  }
  static remux(input: string, output: string, caFile: string = ''): Session {
    const id = ++FFmpeg.sequence;
    const result = native.run(id, 'remux', input, output, 'copy', 'copy', '', '', caFile).then((): void => {});
    return { id, result };
  }
  static transcode(options: TranscodeOptions): Session {
    const id = ++FFmpeg.sequence;
    const result = native.run(id, 'transcode', options.input, options.output,
      options.videoCodec ?? 'mpeg4', options.audioCodec ?? 'aac',
      options.videoFilter ?? '', options.audioFilter ?? '', options.caFile ?? '').then((): void => {});
    return { id, result };
  }
  // Experimental command-test HAR only. Arguments exclude the executable name.
  // timeoutSeconds: integer 0..2147483647; 0 disables total timeout. Default: 300.
  static execute(args: string[], timeoutSeconds: number = 300): CommandSession {
    const id = ++FFmpeg.sequence;
    const result = native.execute(id, args, timeoutSeconds).then((value: string): CommandResult => {
      return JSON.parse(value) as CommandResult;
    });
    return { id, result };
  }
  // Poll while active (e.g. every 150 ms); use result.logs after completion.
  // Null means this session has completed or does not exist. Buffer limit: 256 KiB.
  static readCommandLogs(id: number): CommandLogSnapshot | null {
    return JSON.parse(native.readCommandLogs(id)) as CommandLogSnapshot | null;
  }
  static cancel(id: number): void { native.control(id, true); }
  // Latest input packet timestamp in microseconds; -1 after the session ends.
  static progressUs(id: number): number { return native.control(id, false); }
}
