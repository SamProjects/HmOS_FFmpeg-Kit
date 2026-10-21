export const getBuildInfo: () => string;
export const getCapabilities: () => string;
export const run: (id: number, operation: string, input: string, output: string,
  videoCodec: string, audioCodec: string, videoFilter: string, audioFilter: string, caFile: string) => Promise<string>;
export const control: (id: number, cancel: boolean) => number;

// timeoutSeconds is an integer 0..2147483647; 0 disables the total timeout.
export const execute: (id: number, args: string[], timeoutSeconds: number) => Promise<string>;

export const readCommandLogs: (id: number) => string;
