project('speech-provider-piper',
        'rust',
        version: files('VERSION'),
        license: 'GPL3',
	meson_version : '>= 0.58')

version = meson.project_version()

prefix = get_option('prefix')
bindir = prefix / get_option('bindir')
localedir = prefix / get_option('localedir')
datadir = prefix / get_option('datadir')
pkgdatadir = datadir / meson.project_name()

application_id = 'ai.piper.Speech.Provider'

find_program('cargo', required: true)
cargo_script = find_program('cargo.py')

subdir('src')

config = configuration_data()
config.set('bindir', bindir)

# DBus service
configure_file(
  input: 'data/ai.piper.Speech.Provider.service.in',
  output: 'ai.piper.Speech.Provider.service',
  configuration: config,
)
install_data(
  meson.current_build_dir() / 'ai.piper.Speech.Provider.service',
  install_dir: get_option('datadir') / 'dbus-1/services',
)

install_data(
  'data' / 'ai.piper.Speech.Provider.metainfo.xml',
  install_dir: get_option('datadir') / 'metainfo',
)
