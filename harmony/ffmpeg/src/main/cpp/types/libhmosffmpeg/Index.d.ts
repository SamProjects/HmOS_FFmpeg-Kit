export const getBuildInfo: () => string;
export const getCapabilities: () => string;
export const run: (id: number, operation: string, input: string, output: string,
  videoCodec: string, audioCodec: string, videoFilter: string, audioFilter: string, caFile: string) => Promise<string>;
export const control: (id: number, cancel: boolean) => number;
