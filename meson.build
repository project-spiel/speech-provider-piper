project('speech-provider-piper',
  license: 'GPL-3',
  version: run_command(
    'python3', '-c',
    'from speech_provider_piper.version import __version__; print(__version__, end="")',
    check: true
  ).stdout(),
)

# Dependencies
python_module = import('python')
py = python_module.find_installation('python3', required: true, modules: [
  'gi', 'piper', 'dasbus'
])

# Configuration used in template files
config = configuration_data()
config.set('python_path', py.path())
config.set('bindir', get_option('prefix') / get_option('bindir'))
config.set('voices_dir', get_option('prefix') / get_option('datadir') / 'piper/voices')

configure_file(
  input: 'speech-provider-piper.py.in',
  output: 'speech-provider-piper',
  configuration: config,
  install_mode: 'rwxr-xr-x',
  install_dir: get_option('bindir'),
)

# Python module
install_subdir(
  'speech_provider_piper',
  install_dir: py.get_install_dir(),
)

# DBus service
configure_file(
  input: 'data/ai.piper.Speech.Provider.service.in',
  output: 'ai.piper.Speech.Provider.service',
  configuration: config,
)
install_data(
  meson.current_build_dir() / 'ai.piper.Speech.Provider.service',
  install_dir: get_option('prefix') / get_option('datadir') / 'dbus-1/services',
)
