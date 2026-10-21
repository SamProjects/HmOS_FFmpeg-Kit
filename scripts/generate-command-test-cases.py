#!/usr/bin/env python3
"""Shared offline command matrix consumed by the ArkTS app and host adapter tests."""
import json
from pathlib import Path


def cases():
    result = []
    def add(label, args, output='', **kw):
        result.append(dict(id=f'{len(result)+1:02}', label=label, args=args,
                           output=output, expected='success', timeout=45,
                           cancelMs=-1, repeatCancel=False, concurrent=False,
                           requireLive=False, requireProgress=False,
                           videoCodec='', audioCodec='', width=0, height=0,
                           sampleRate=0, channels=0, minDuration=0.0, maxDuration=0.0,
                           verifyDecode=False, requireTruncated=False) | kw)
    def media(label, opts, name, source='{VIDEO}', **kw):
        output='{DIR}/'+name
        add(label, ['-y','-i',source,'-t','3',*opts,output], output, **kw)
    add('版本及日志', ['-version'])
    add('编码器列表及长日志', ['-encoders'])
    add('解码器列表', ['-decoders'])
    add('滤镜列表', ['-filters'])
    add('非法参数及错误日志', ['-not_an_ffmpeg_option'], expected='error')
    add('非法参数后恢复', ['-version'])
    add('输入文件不存在', ['-i','{DIR}/missing.mp4','-f','null','{DIR}/missing.null'], expected='error')
    add('不存在的编码器', ['-y','-i','{VIDEO}','-c:v','not_a_codec','{DIR}/bad.mp4'], expected='error')
    add('非法滤镜', ['-y','-i','{VIDEO}','-vf','not_a_filter','{DIR}/bad-filter.mp4'], expected='error')
    add('错误后再次恢复', ['-version'])
    media('原片 AV1 全片重封装', ['-map','0','-c','copy'], 'original-remux.mp4',source='{ORIGINAL}', minDuration=299,maxDuration=302,videoCodec='av1',audioCodec='aac')
    result[-1]['args'] = ['-y','-i','{ORIGINAL}','-map','0','-c','copy',result[-1]['output']]
    media('原片 AV1 片段复制', ['-map','0','-c','copy'], 'original-clip.mkv',source='{ORIGINAL}',videoCodec='av1',audioCodec='aac',minDuration=2,maxDuration=6)
    media('原片音频无损提取', ['-vn','-c:a','copy'], 'original-audio.m4a',source='{ORIGINAL}',audioCodec='aac',minDuration=2,maxDuration=4)
    media('原片音频转 PCM 16k 单声道', ['-vn','-c:a','pcm_s16le','-ar','16000','-ac','1'], 'original-audio.wav',source='{ORIGINAL}',audioCodec='pcm_s16le',sampleRate=16000,channels=1,minDuration=2,maxDuration=4)
    media('原片音频重新编码 AAC', ['-vn','-c:a','aac','-b:a','64k'], 'original-aac.m4a',source='{ORIGINAL}',audioCodec='aac')
    add('原片 AV1 实际解码能力', ['-i','{ORIGINAL}','-t','1','-an','-f','null','{DIR}/av1.null'], expected='capability')
    media('兼容素材重封装 MKV', ['-c','copy'], 'copy.mkv',videoCodec='mpeg4',audioCodec='aac',minDuration=2,maxDuration=4)
    media('MPEG4 视频和 AAC 音频转码', ['-c:v','mpeg4','-q:v','6','-c:a','aac'], 'transcode.mp4',videoCodec='mpeg4',audioCodec='aac',verifyDecode=True,minDuration=2,maxDuration=4)
    media('缩放 160x90', ['-vf','scale=160:90','-c:v','mpeg4','-an'], 'scale.mp4',videoCodec='mpeg4',width=160,height=90,verifyDecode=True)
    media('裁剪 160x120', ['-vf','crop=160:120:0:0','-c:v','mpeg4','-an'], 'crop.mp4',videoCodec='mpeg4',width=160,height=120,verifyDecode=True)
    media('旋转 90 度', ['-vf','transpose=1','-c:v','mpeg4','-an'], 'rotate.mp4',videoCodec='mpeg4',width=180,height=320,verifyDecode=True)
    media('降低帧率到 10fps', ['-vf','fps=10','-c:v','mpeg4','-an'], 'fps.mp4',videoCodec='mpeg4',verifyDecode=True)
    media('灰度滤镜', ['-vf','hue=s=0','-c:v','mpeg4','-an'], 'gray.mp4',videoCodec='mpeg4',verifyDecode=True)
    media('水平翻转', ['-vf','hflip','-c:v','mpeg4','-an'], 'flip.mp4',videoCodec='mpeg4',verifyDecode=True)
    media('复合滤镜与显式映射', ['-filter_complex','[0:v]scale=160:90,hflip[v];[0:a]volume=0.3[a]','-map','[v]','-map','[a]','-c:v','mpeg4','-c:a','aac'], 'complex.mp4',videoCodec='mpeg4',audioCodec='aac',width=160,height=90,verifyDecode=True)
    media('截取 PNG 单帧', ['-frames:v','1','-an','-c:v','png','-update','1'], 'frame.png',videoCodec='png',width=320,height=180)
    media('截取 JPEG 单帧', ['-frames:v','1','-an','-c:v','mjpeg','-update','1'], 'frame.jpg',videoCodec='mjpeg',width=320,height=180)
    media('音频转 WAV 48k 双声道', ['-vn','-c:a','pcm_s16le','-ar','48000','-ac','2'], 'audio.wav',audioCodec='pcm_s16le',sampleRate=48000,channels=2)
    media('音频音量滤镜', ['-vn','-af','volume=0.25','-c:a','pcm_s16le'], 'volume.wav',audioCodec='pcm_s16le')
    media('音频加速 1.5 倍', ['-vn','-af','atempo=1.5','-c:a','pcm_s16le'], 'tempo.wav',audioCodec='pcm_s16le')
    media('视频去音轨', ['-an','-c:v','copy'], 'no-audio.mp4',videoCodec='mpeg4')
    media('中文 空格 分号文件路径', ['-c','copy'], '中文 空格 ; 测试.mp4',videoCodec='mpeg4',audioCodec='aac')
    add('拒绝覆盖已有输出', ['-n','-i','{VIDEO}','-c','copy','{DIR}/copy.mkv'], expected='error')
    media('覆盖失败后强制覆盖恢复', ['-c','copy'], 'copy.mkv',videoCodec='mpeg4')
    add('执行期间实时日志和进度', ['-y','-loglevel','verbose','-stats','-stats_period','0.2','-re','-i','{VIDEO}','-t','3','-c:v','mpeg4','-c:a','aac','{DIR}/live.mp4'], '{DIR}/live.mp4', requireLive=True, requireProgress=True,videoCodec='mpeg4',audioCodec='aac')
    for label,delay,repeat in [('立即取消',0,False),('处理中取消',700,False),('重复取消',500,True)]:
        add(label,['-y','-re','-stream_loop','-1','-i','{VIDEO}','-t','60','-c:v','mpeg4','-c:a','aac','{DIR}/cancel.mp4'],expected='cancel',cancelMs=delay,repeatCancel=repeat)
        add(label+'后恢复',['-version'])
    add('超时中断', ['-y','-re','-stream_loop','-1','-i','{VIDEO}','-t','60','-c','copy','{DIR}/timeout.mp4'],expected='timeout',timeout=1)
    add('超时后恢复', ['-version'])
    add('执行期间拒绝并发调用', ['-y','-re','-i','{VIDEO}','-t','2','-c','copy','{DIR}/exclusive.mp4'],concurrent=True)
    add('并发拒绝后恢复', ['-version'])
    for arg in ['-stdin','-report','-progress','pipe:1']:
        add('拒绝进程级或标准IO参数 '+arg,[arg],expected='reject')
    for n in range(5):
        media(f'连续转码状态复位 {n+1}/5',['-vf','scale=160:90','-c:v','mpeg4','-an'],f'repeat-{n}.mp4',videoCodec='mpeg4',width=160,height=90,verifyDecode=True)
    add('非法流映射', ['-i','{VIDEO}','-map','0:99','-f','null','{DIR}/bad-map.null'],expected='error')
    add('无法创建输出文件', ['-y','-i','{VIDEO}','-c','copy','{DIR}/missing-folder/output.mp4'],expected='error')
    add('完整视频音频解码到空输出', ['-i','{VIDEO}','-f','null','{DIR}/decode.null'])
    add('静默日志级别', ['-v','quiet','-i','{VIDEO}','-t','1','-f','null','{DIR}/quiet.null'])
    add('日志上限及截断标记', ['-loglevel','verbose','-debug_ts','-stream_loop','2','-i','{VIDEO}','-t','15','-f','null','{DIR}/bounded.null'],requireTruncated=True)
    add('长日志后恢复及日志隔离', ['-version'])
    return result

if __name__ == '__main__':
    target=Path(__file__).resolve().parents[1]/'examples/consumer/entry/src/main/resources/rawfile/command-cases.json'
    target.write_text(json.dumps(cases(),ensure_ascii=False,indent=2)+'\n')
    print(f'{len(cases())} cases -> {target}')
