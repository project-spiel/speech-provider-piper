sources = files(
    'main.rs',
)

app_name = meson.project_name()

if get_option('offline')
  offline = '--offline'
else
  offline = ''  
endif

voices_dir = get_option('voices_dir')
if voices_dir == ''
  voices_dir = get_option('prefix') / get_option('datadir') / 'piper/voices'
endif

custom_target('speech-provider-piper',
              build_by_default: true,
              input: [sources, meson.project_source_root() / 'Cargo.toml'],
              output: app_name,
              console: true,
              install: true,
              install_dir: bindir,
              command: [cargo_script,
                  meson.project_build_root(),
                  meson.project_source_root(),
                  '@OUTPUT@',
                  app_name,
                  voices_dir,
                  offline])
