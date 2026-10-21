import { UIAbility } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
export default class EntryAbility extends UIAbility {
  onWindowStageCreate(stage: window.WindowStage): void {
    stage.loadContent('pages/Index', (error): void => {
      if (error.code) console.error('FFmpegTest: loadContent failed: ' + JSON.stringify(error));
    });
  }
}
