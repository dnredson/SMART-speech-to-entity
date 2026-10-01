import { useEffect, useRef, useState } from "react";

interface VoiceRecorderProps {
  disabled?: boolean;
  onRecorded: (blob: Blob, mimeType: string) => Promise<void>;
}

const MAX_RECORDING_SECONDS = 120;

export function VoiceRecorder({ disabled = false, onRecorded }: VoiceRecorderProps) {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const timerRef = useRef<number | null>(null);
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => () => {
    if (timerRef.current !== null) window.clearInterval(timerRef.current);
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  async function startRecording() {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Este navegador não oferece gravação de áudio.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const preferred = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"]
        .find((type) => MediaRecorder.isTypeSupported(type));
      const recorder = preferred === undefined ? new MediaRecorder(stream) : new MediaRecorder(stream, { mimeType: preferred });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const mimeType = recorder.mimeType || preferred || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: mimeType });
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        void onRecorded(blob, mimeType);
      };

      recorder.start(500);
      setSeconds(0);
      setRecording(true);
      timerRef.current = window.setInterval(() => {
        setSeconds((value) => {
          const next = value + 1;
          if (next >= MAX_RECORDING_SECONDS) {
            window.setTimeout(() => stopRecording(), 0);
          }
          return next;
        });
      }, 1000);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível acessar o microfone.");
    }
  }

  function stopRecording() {
    const recorder = mediaRecorderRef.current;
    if (recorder === null || recorder.state === "inactive") return;
    recorder.stop();
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setRecording(false);
  }

  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const remaining = (seconds % 60).toString().padStart(2, "0");

  return (
    <div className="voice-box">
      <button
        className={`voice-button${recording ? " is-recording" : ""}`}
        type="button"
        disabled={disabled}
        onClick={recording ? stopRecording : () => void startRecording()}
        aria-pressed={recording}
      >
        <span className="voice-icon" aria-hidden="true">{recording ? "■" : "●"}</span>
        <span>{recording ? "Toque para finalizar" : "Toque para falar"}</span>
      </button>
      <p className="voice-hint">
        {recording
          ? `Gravando ${minutes}:${remaining} · máximo 02:00`
          : "Diga data, hora de início e duração. Na fertirrigação, inclua produto, kg/ha e litros de solução."}
      </p>
      {error !== null && <p className="form-error">{error}</p>}
    </div>
  );
}
