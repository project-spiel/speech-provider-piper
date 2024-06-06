use std::env;
use std::fs;
use std::path::Path;

fn main() {
    let out_dir = env::var_os("OUT_DIR").unwrap();
    let voices_dir = match env::var_os("VOICES_DIR") {
      Some(dir) => dir,
      None => "voices".into()
    };
    let dest_path = Path::new(&out_dir).join("voices_path.txt");
    fs::write(
        &dest_path,
        voices_dir.to_str().unwrap()
    ).unwrap();
    println!("cargo::rerun-if-changed=build.rs");
    println!("cargo::rerun-if-env-changed=VOICES_DIR");
}