import React, { useState, useEffect } from 'react';

export default function MicButton({ onSpeechEnd }) {
  const [isListening, setIsListening] = useState(false);
  const [recognition, setRecognition] = useState(null);

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const rec = new SpeechRecognition();
      rec.continuous = false;
      rec.interimResults = false;
      rec.lang = 'en-IN'; // Indian Legal context is in English (India)

      rec.onstart = () => {
        setIsListening(true);
      };

      rec.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
      };

      rec.onend = () => {
        setIsListening(false);
      };

      rec.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if (onSpeechEnd) {
          onSpeechEnd(transcript);
        }
      };

      setRecognition(rec);
    }
  }, [onSpeechEnd]);

  const toggleListen = () => {
    if (!recognition) {
      alert('Browser does not support Web Speech API.');
      return;
    }

    if (isListening) {
      recognition.stop();
    } else {
      recognition.start();
    }
  };

  return (
    <button
      type="button"
      onClick={toggleListen}
      className="btn-icon"
      style={{
        background: isListening ? 'rgba(239, 68, 68, 0.1)' : 'transparent',
        borderColor: isListening ? 'rgba(239, 68, 68, 0.3)' : 'var(--border-default)',
        color: isListening ? 'var(--color-danger)' : 'var(--text-muted)',
      }}
      title={isListening ? 'Listening... Click to stop' : 'Use voice input'}
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
        <line x1="12" x2="12" y1="19" y2="22"/>
      </svg>
    </button>
  );
}
