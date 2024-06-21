use glob::{glob, GlobError, PatternError};
use serde::Deserialize;
use sonata_piper::PiperSynthesisConfig;
use sonata_synth::{
    Audio, AudioOutputConfig, SonataError, SonataModel, SonataResult, SonataSpeechSynthesizer,
};
use speechprovider::*;
use std::collections::HashMap;
use std::fs::File;
use std::future::pending;
use std::os::fd::IntoRawFd;
use std::path::Path;
use std::result::Result;
use std::sync::Arc;
use std::{env, thread};
use zbus::zvariant::OwnedFd;
use zbus::{dbus_interface, ConnectionBuilder, MessageHeader, SignalContext};

static INIT_ORT_ENVIRONMENT: std::sync::Once = std::sync::Once::new();

static VOICES_DIR: &str = include_str!(concat!(env!("OUT_DIR"), "/voices_path.txt"));

fn init_ort_environment() {
    INIT_ORT_ENVIRONMENT.call_once(|| {
        let execution_providers = [
            #[cfg(feature = "cuda")]
            ort::ExecutionProviderDispatch::CUDA(Default::default()),
            ort::ExecutionProviderDispatch::CPU(Default::default()),
        ];
        ort::init()
            .with_name("sonata")
            .with_execution_providers(execution_providers)
            .commit()
            .expect("Failed to initialize onnxruntime");
    });
}

fn param_to_percent(value: f32, min: f32, max: f32) -> u8 {
    ((value - min) / (max - min) * 100.0f32).round() as u8
}

#[derive(Clone, Debug, zbus::DBusError)]
#[dbus_error(prefix = "ai.piper.Speech.Provider.Error")]
pub enum PiperProviderError {
    Failed,
}

impl From<std::io::Error> for PiperProviderError {
    fn from(_: std::io::Error) -> Self {
        Self::Failed
    }
}

impl From<PatternError> for PiperProviderError {
    fn from(_: PatternError) -> Self {
        Self::Failed
    }
}

impl From<GlobError> for PiperProviderError {
    fn from(_: GlobError) -> Self {
        Self::Failed
    }
}

impl From<SonataError> for PiperProviderError {
    fn from(_: SonataError) -> Self {
        Self::Failed
    }
}

impl From<Box<dyn std::any::Any>> for PiperProviderError {
    fn from(_: Box<dyn std::any::Any>) -> Self {
        Self::Failed
    }
}

impl From<anyhow::Error> for PiperProviderError {
    fn from(_: anyhow::Error) -> Self {
        Self::Failed
    }
}

#[derive(Deserialize, Default, Debug)]
pub struct AudioConfig {
    pub sample_rate: u32,
    pub quality: Option<String>,
}

#[derive(Clone, Deserialize, Default, Debug)]
pub struct Language {
    code: String,
}

#[derive(Deserialize, Default, Debug)]
pub struct ModelConfig {
    pub dataset: Option<String>,
    pub key: Option<String>,
    pub language: Option<Language>,
    pub audio: AudioConfig,
    pub num_speakers: u32,
    pub speaker_id_map: HashMap<String, i64>,
    pub streaming: Option<bool>,
}

fn load_voices_from_model(
    voices_path: &std::path::PathBuf,
    voice_path: &Path,
) -> Option<Vec<(String, String, String, u64, Vec<String>)>> {
    let file = File::open(voice_path.to_str()?).ok()?;
    let model_config: ModelConfig = match serde_json::from_reader(file.try_clone().ok()?) {
        Ok(config) => config,
        Err(why) => {
            eprintln!(
                "Faild to parse model config from file: `{}`. Caused by: `{}`",
                voice_path.display(),
                why
            );
            return None;
        }
    };

    let sample_rate = model_config.audio.sample_rate;
    let audio_format = format!("audio/x-spiel,format=S16LE,channels=1,rate={sample_rate}");
    let identifier = String::from(
        voice_path
            .parent()?
            .strip_prefix(voices_path)
            .ok()?
            .to_str()?,
    );

    let mut features = 0;

    if model_config.streaming {
        features |= VoiceFeature::EVENTS_SENTENCE;
    }

    let mut name = match model_config.dataset {
        Some(name) => name,
        None => String::from(model_config.key.clone()?.split("-").nth(1)?),
    };

    if model_config.streaming.is_some_and(|x| x)  {
        name = format!("{name} RT");
    }

    let language = match model_config.language {
        Some(lang) => lang.code,
        None => String::from(model_config.key?.split("-").next()?),
    };

    let languages = vec![String::from(language.clone())];
    let mut voices: Vec<(String, String, String, u64, Vec<String>)> = model_config
        .speaker_id_map
        .iter()
        .map(|(speaker, speaker_idx)| {
            let speaker_name = format!("{}: ({})", &name, speaker);
            let speaker_ident = format!("{}#{}", &identifier, speaker_idx);
            (
                speaker_name,
                speaker_ident,
                audio_format.clone(),
                features,
                languages.clone(),
            )
        })
        .collect();
    if voices.is_empty() {
        voices.push((name, identifier, audio_format, features, languages));
    }
    Some(voices)
}

struct Speaker {
    synths: HashMap<String, Arc<SonataSpeechSynthesizer>>,
}

impl Speaker {
    fn new() -> Speaker {
        Speaker {
            synths: HashMap::new(),
        }
    }
}

#[dbus_interface(name = "org.freedesktop.Speech.Provider")]
impl Speaker {
    #[dbus_interface(property)]
    async fn name(&self) -> String {
        "Piper".to_string()
    }

    #[dbus_interface(property)]
    async fn voices(
        &self,
    ) -> Result<Vec<(String, String, String, u64, Vec<String>)>, zbus::fdo::Error> {
        let mut voices = Vec::new();

        let voices_path = Path::new(VOICES_DIR)
            .canonicalize()
            .map_err(|e| zbus::fdo::Error::IOError(e.to_string()))?;
        let json_glob = voices_path.join("*/*.json");
        let os_str = json_glob
            .to_str()
            .ok_or(zbus::fdo::Error::IOError(String::from("eh")))?;

        for entry in glob(&os_str).map_err(|e| zbus::fdo::Error::IOError(e.to_string()))? {
            let voice_path_str = entry.map_err(|e| zbus::fdo::Error::IOError(e.to_string()))?;
            let voice_path = Path::new(&voice_path_str);
            match load_voices_from_model(&voices_path, voice_path).as_mut() {
                Some(model_voices) => {
                    voices.append(model_voices);
                }
                None => (),
            }
        }

        Ok(voices)
    }

    async fn synthesize(
        &mut self,
        fd: OwnedFd,
        utterance: &str,
        voice_id: &str,
        pitch: f32,
        rate: f32,
        is_ssml: bool,
        _language: &str,
        #[zbus(header)] _header: MessageHeader<'_>,
        #[zbus(signal_context)] _ctxt: SignalContext<'_>,
    ) -> Result<(), PiperProviderError> {
        let mut tokenized_id = voice_id.split("#");
        let identifier = tokenized_id.next().ok_or(PiperProviderError::Failed)?;
        let voice_path = {
            let mut path = Path::new(VOICES_DIR).canonicalize()?;
            path.push(identifier);
            path.push("*.json");
            let entries: Vec<std::path::PathBuf> =
                glob(path.to_str().ok_or(PiperProviderError::Failed)?)?
                    .flatten()
                    .collect();
            if entries.len() != 1 {
                eprintln!("Expected only one json in voice directory");
                return Err(PiperProviderError::Failed);
            }
            entries.first().ok_or(PiperProviderError::Failed)?.clone()
        };

        let synth: Arc<SonataSpeechSynthesizer> = {
            match self.synths.get(voice_id) {
                Some(synth) => synth.clone(),
                None => {
                    let voice = sonata_piper::from_config_path(&voice_path)?;
                    let synth = Arc::new(SonataSpeechSynthesizer::new(voice)?);
                    self.synths.insert(String::from(voice_id), synth.clone());
                    synth
                }
            }
        };

        let mut synth_config: PiperSynthesisConfig =
            *synth.get_default_synthesis_config()?.downcast()?;
        synth_config.speaker = tokenized_id
            .next()
            .map_or_else(|| None, |v| v.parse::<i64>().ok());
        synth.set_fallback_synthesis_config(&synth_config)?;

        let text_to_speak = if is_ssml {
            String::from(parse_ssml(utterance)?.get_text())
        } else {
            String::from(utterance)
        };

        let output_config = AudioOutputConfig {
            rate: Some(param_to_percent(rate, 0.5f32, 5.5f32)),
            pitch: Some(param_to_percent(pitch, 0.5f32, 1.5f32)),
            volume: Some(100),
            appended_silence_ms: Some(0),
        };

        thread::spawn(move || {
            let stream_writer = StreamWriter::new(fd.into_raw_fd());
            // let mut f = File::from(std::os::fd::OwnedFd::from(fd));
            let stream: Box<dyn Iterator<Item = SonataResult<Audio>>> = if synth
                .supports_streaming_output()
            {
                Box::new(
                    synth
                        .synthesize_streamed(text_to_speak, Some(output_config), 100, 3)
                        .unwrap()
                        .map(|res| res.map(|samples| Audio::new(samples, 0, None))),
                )
            } else {
                Box::new(
                    synth
                        .synthesize_parallel(text_to_speak, Some(output_config))
                        .unwrap(),
                )
            };

            stream_writer.send_stream_header();
            for result in stream {
                let audio = result.unwrap();
                let wav_bytes = audio.as_wave_bytes();
                if let Some((start, end)) = audio.sentence_boundary {
                    stream_writer.send_event(
                        EventType::Sentence,
                        start.try_into().unwrap(),
                        end.try_into().unwrap(),
                        "",
                    );
                }
                for chunk in wav_bytes.chunks(8192) {
                    stream_writer.send_audio(&chunk);
                }
            }
        });
        Ok(())
    }
}

#[async_std::main]
async fn main() -> zbus::Result<()> {
    init_ort_environment();

    let _conn = ConnectionBuilder::session()?
        .name("ai.piper.Speech.Provider")?
        .serve_at("/ai/piper/Speech/Provider", Speaker::new())?
        .build()
        .await?;

    pending::<()>().await;

    Ok(())
}
