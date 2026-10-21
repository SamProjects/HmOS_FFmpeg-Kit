#!/usr/bin/env python3
"""Generate a recorded experimental fftools adapter; never alter pristine input."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('FFmpeg 9.0.2 adapter anchor changed: ' + old[:100])
    return text.replace(old, new, 1)


def prepare(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Adapter source and destination must be separate trees')
    if (source / 'RELEASE').read_text().strip() != '9.0.2':
        raise ValueError('Only the audited FFmpeg 9.0.2 release is supported')
    shutil.copytree(source, destination)
    changes, records = [], {}

    def edit(name, transform):
        original = (source / name).read_text()
        updated = transform(original)
        (destination / name).write_text(updated)
        records[name] = {'before':hashlib.sha256(original.encode()).hexdigest(),
                         'after':hashlib.sha256(updated.encode()).hexdigest()}
        changes.extend(difflib.unified_diff(original.splitlines(True), updated.splitlines(True),
                                          fromfile='a/' + name, tofile='b/' + name))

    def main(text):
        text = replace_once(text, 'int main(int argc, char **argv)', 'int hmos_ffmpeg_main(int argc, char **argv)')
        # No application signal handlers or terminal mutation from library code.
        start = text.index('void term_init(void)\n{')
        end = text.index('\n/* read a key without blocking */', start)
        text = text[:start] + 'void term_init(void) {}\n' + text[end:]
        text = replace_once(text, '        exit(123);', '        return; /* never terminate the host application */')
        text = replace_once(text, '    setvbuf(stderr,NULL,_IONBF,0); /* win32 runtime needs this */', '''    extern void hmos_reset_options(void);
    hmos_reset_options();
    nb_input_files = nb_output_files = nb_filtergraphs = nb_decoders = 0;
    input_files = NULL; output_files = NULL; filtergraphs = NULL; decoders = NULL;
    vstats_file = NULL; progress_avio = NULL;
    received_sigterm = received_nb_signals = ffmpeg_exited = 0;
    atomic_store(&transcode_init_done, 0);
    atomic_store(&nb_output_dumped, 0);
    copy_ts_first_pts = AV_NOPTS_VALUE;
    current_time = (BenchmarkTimeStamps){0};''')
        text = replace_once(text, '    return received_nb_signals > atomic_load(&transcode_init_done);',
                            '    return hmos_cmd_cancelled() || received_nb_signals > atomic_load(&transcode_init_done);')
        text = replace_once(text, '        if (received_nb_signals)\n            break;',
                            '        if (received_nb_signals || hmos_cmd_cancelled())\n            break;')
        text = replace_once(text, '    static int64_t last_time = -1;\n    static int first_report = 1;',
                            '    int64_t *last_time_ptr = &hmos_report_last_time;\n    int *first_report_ptr = &hmos_report_first;')
        # These state variables used to survive between invocations.
        report_start = text.index('static void print_report(')
        report_end = text.index('\nstatic void ', report_start + 1)
        report = text[report_start:report_end]
        report = re.sub(r'\blast_time\b', '(*last_time_ptr)', report)
        report = re.sub(r'\bfirst_report\b', '(*first_report_ptr)', report)
        report = replace_once(report, '    AVBPrint buf, buf_script;',
                              '    hmos_cmd_progress(pts);\n    AVBPrint buf, buf_script;')
        text = text[:report_start] + report + text[report_end:]
        text = replace_once(text, 'static int64_t copy_ts_first_pts = AV_NOPTS_VALUE;',
                            'static int64_t copy_ts_first_pts = AV_NOPTS_VALUE;\nstatic int64_t hmos_report_last_time = -1;\nstatic int hmos_report_first = 1;')
        text = replace_once(text, '    current_time = (BenchmarkTimeStamps){0};',
                            '    current_time = (BenchmarkTimeStamps){0};\n    hmos_report_last_time = -1; hmos_report_first = 1;')
        text = replace_once(text, '    sch_free(&sch);', '    sch_free(&sch);\n    if (progress_avio) avio_closep(&progress_avio);')
        return text

    def options(text):
        block = text[text.index('HWDevice *filter_hw_device;'):text.index('// this struct is passed')]
        reset = []
        for line in block.splitlines():
            match = re.fullmatch(r'(?:static )?(?:HWDevice\s*\*|char\s*\*|float\s+|int64_t\s+|int\s+)(\w+)\s*(?:=\s*(.*?))?;', line.strip())
            if match:
                name, value = match.groups()
                reset.append(f'    {name} = {value or "0"};')
        if len(reset) != 32:
            raise ValueError(f'Unexpected option globals: {len(reset)}; audit reset list')
        reset += ['    stdin_interaction = 0;', '    hide_banner = 0;']
        start = text.index('int assert_file_overwrite(')
        end = text.index('\n}', start) + 2
        text = text[:start] + text[start:end].replace('return AVERROR_EXIT;', 'return AVERROR(EEXIST);') + text[end:]
        return text + '\nvoid hmos_reset_options(void);\nvoid hmos_reset_options(void)\n{\n' + '\n'.join(reset) + '\n}\n'

    edit('fftools/ffmpeg.c', main)
    edit('fftools/ffmpeg_opt.c', options)
    edit('fftools/cmdutils.c', lambda s: replace_once(s, '    vfprintf(stdout, fmt, vl);',
                                                    '    hmos_cmd_avlog(ptr, level, fmt, vl);'))
    # Per-process report callback/file ownership is outside this serial test API.
    edit('fftools/opt_common.c', lambda s: replace_once(s,
         'int init_report(const char *env, FILE **file)\n{',
         'int init_report(const char *env, FILE **file)\n{\n    return AVERROR(ENOSYS); /* disabled in embedded test build */'))
    (destination / 'hmos-command.patch').write_text(''.join(changes))
    (destination / 'hmos-command-adaptation.json').write_text(json.dumps(
        {'experimental':True, 'version':'9.0.2', 'files':records}, indent=2) + '\n')
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    prepare(args.source, args.destination)
