import { FFmpeg } from '@samprojects/hmos-ffmpeg';
@Entry
@Component
struct Index {
  @State message: string = 'Loading FFmpeg';
  aboutToAppear(): void {
    try { this.message = JSON.stringify(FFmpeg.getBuildInfo()); }
    catch (e) { this.message = String(e); }
  }
  build() {
    Column() { Text(this.message).padding(24) }.width('100%').height('100%')
  }
}
