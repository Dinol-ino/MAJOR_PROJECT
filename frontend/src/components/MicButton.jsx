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
      className={`mic-button ${isListening ? 'listening' : ''}`}
      style={{
        background: isListening ? 'rgba(239, 68, 68, 0.2)' : 'rgba(255, 255, 255, 0.05)',
        border: `1px solid ${isListening ? 'var(--danger-color)' : 'var(--panel-border)'}`,
        borderRadius: '50%',
        width: '44px',
        height: '44px',
        display: 'flex',
        align-items: 'center',
        justifyContent: 'center',
        fontSize: '1.2rem',
        boxShadow: isListening ? '0 0 12px var(--danger-color)' : 'none',
      }}
      title={isListening ? 'Listening... Click to stop' : 'Use voice input'}
    >
      {isListening ? '🎙️' : '🎤'}
    </button>
  );
}
