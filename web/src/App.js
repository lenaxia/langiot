import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

// Language codes for dropdown selections
const languageCodes = [
  { code: 'en', name: 'English' },
  { code: 'zh-TW', name: 'Chinese (Mandarin/Taiwan)' },
  { code: 'zh-CN', name: 'Chinese (Simplified)' },
  { code: 'zh', name: 'Chinese (Mandarin)' },
  { code: 'af', name: 'Afrikaans' },
  { code: 'ar', name: 'Arabic' },
  { code: 'bg', name: 'Bulgarian' },
  { code: 'bn', name: 'Bengali' },
  { code: 'bs', name: 'Bosnian' },
  { code: 'ca', name: 'Catalan' },
  { code: 'cs', name: 'Czech' },
  { code: 'da', name: 'Danish' },
  { code: 'de', name: 'German' },
  { code: 'el', name: 'Greek' },
  { code: 'es', name: 'Spanish' },
  { code: 'et', name: 'Estonian' },
  { code: 'fi', name: 'Finnish' },
  { code: 'fr', name: 'French' },
  { code: 'gu', name: 'Gujarati' },
  { code: 'hi', name: 'Hindi' },
  { code: 'hr', name: 'Croatian' },
  { code: 'hu', name: 'Hungarian' },
  { code: 'id', name: 'Indonesian' },
  { code: 'is', name: 'Icelandic' },
  { code: 'it', name: 'Italian' },
  { code: 'iw', name: 'Hebrew' },
  { code: 'ja', name: 'Japanese' },
  { code: 'jw', name: 'Javanese' },
  { code: 'km', name: 'Khmer' },
  { code: 'kn', name: 'Kannada' },
  { code: 'ko', name: 'Korean' },
  { code: 'la', name: 'Latin' },
  { code: 'lv', name: 'Latvian' },
  { code: 'ml', name: 'Malayalam' },
  { code: 'mr', name: 'Marathi' },
  { code: 'ms', name: 'Malay' },
  { code: 'my', name: 'Myanmar (Burmese)' },
  { code: 'ne', name: 'Nepali' },
  { code: 'nl', name: 'Dutch' },
  { code: 'no', name: 'Norwegian' },
  { code: 'pl', name: 'Polish' },
  { code: 'pt', name: 'Portuguese' },
  { code: 'ro', name: 'Romanian' },
  { code: 'ru', name: 'Russian' },
  { code: 'si', name: 'Sinhala' },
  { code: 'sk', name: 'Slovak' },
  { code: 'sq', name: 'Albanian' },
  { code: 'sr', name: 'Serbian' },
  { code: 'su', name: 'Sundanese' },
  { code: 'sv', name: 'Swedish' },
  { code: 'sw', name: 'Swahili' },
  { code: 'ta', name: 'Tamil' },
  { code: 'te', name: 'Telugu' },
  { code: 'th', name: 'Thai' },
  { code: 'tl', name: 'Filipino' },
  { code: 'tr', name: 'Turkish' },
  { code: 'uk', name: 'Ukrainian' },
  { code: 'ur', name: 'Urdu' },
  { code: 'vi', name: 'Vietnamese' },
  // ...other languages
];


function App() {
  const [showConfig, setShowConfig] = useState(false);
  const [error, setError] = useState('');
  const [errorConfig, setErrorConfig] = useState('');
  const [formType, setFormType] = useState('translation');
  const [localizations, setLocalizations] = useState([]);
  const [text, setText] = useState('');
  const [language, setLanguage] = useState('');
  const [translations, setTranslations] = useState([]);
  const [audio, setAudio] = useState(null);
  const [jsonDisplay, setJsonDisplay] = useState('');
  const [serverName, setServerName] = useState('');
  const [apiToken, setApiToken] = useState('');

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await axios.get('/get_config');
        setServerName(response.data.ServerName);
        setApiToken(response.data.ApiToken);
      } catch (error) {
        console.error('Error fetching configuration:', error);
        setErrorConfig(`Error fetching configuration: ${error.message}`);
      }
    };

    fetchConfig();
    if (formType === 'localization') {
      setLocalizations([{ language: '', value: '' }]);
    } else {
      setText('');
      setLanguage('');
      setTranslations(['']);
    }
  }, [formType]);

  const handleInputChange = (event, key) => {
    if (key === 'text') {
      setText(event.target.value);
    } else {
      setLanguage(event.target.value);
    }
  };

  const handleLocalizationChange = (index, key, value) => {
    const updatedLocalizations = [...localizations];
    updatedLocalizations[index][key] = value;
    setLocalizations(updatedLocalizations);
  };

  const handleTranslationChange = (index, value) => {
    const updatedTranslations = [...translations];
    updatedTranslations[index] = value;
    setTranslations(updatedTranslations);
  };

  const addLocalizationOrTranslation = () => {
    if (formType === 'localization' && localizations.length < 5) {
      setLocalizations([...localizations, { language: '', value: '' }]);
    } else if (formType === 'translation' && translations.length < 5) {
      setTranslations([...translations, '']);
    }
  };

  const isValidJson = () => {
    if (formType === 'localization') {
      return localizations.every(loc => loc.language && loc.value);
    } else {
      return text && language && translations.every(t => t);
    }
  };

  const generateJson = () => {
    setError('');
    if (formType === 'localization') {
      return JSON.stringify({ localization: localizations.reduce((acc, loc) => {
        acc[loc.language] = loc.value;
        return acc;
      }, {})});
    } else {
      return JSON.stringify({
        text,
        language,
        translations
      });
    }
  };

  const performHttpRequest = async () => {
    setAudio(null)
    if (!isValidJson()) {
      alert('Please ensure all fields have text and languages selected');
      return;
    }
  
    try {
      const jsonStr = generateJson();
      console.log('Sending JSON:', jsonStr);
      setJsonDisplay(jsonStr);
      
      // Parse the JSON string into an object
      const jsonData = JSON.parse(jsonStr);
  
      // Send the JSON object directly
      const response = await axios.post('/perform_http_request', jsonData, { responseType: 'blob' });
      console.log('Received response:', response);
  
      if (response.data) {
        const url = URL.createObjectURL(response.data);
        console.log('Generated URL:', url);
        playAudio(url);
        setAudio(url);
      } else {
        console.error('No data in response');
      }
    } catch (error) {
      console.error('Error performing HTTP request:', error);
      setError(`Error: ${error.response ? error.response.status : ''} ${error.message}`);
    }
  };
  
  
  const playAudio = async (audioData) => {
    try {
      const formData = new FormData();
      formData.append('audioData', new Blob([audioData], { type: 'audio/mpeg' }));
  
      await axios.post('/play_audio', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
    } catch (error) {
      console.error('Error playing audio:', error);
    }
  };
  

  const handleWriteNFC = async () => {
    if (!isValidJson()) {
      alert('Please fill in all fields correctly.');
      return;
    }

    try {
      const jsonStr = generateJson();
      console.log('Writing NFC with JSON:', jsonStr);
      await axios.post('/handle_write', { json_str: jsonStr });
      alert('Write to NFC tag initiated');
    } catch (error) {
      console.error('Error writing to NFC:', error);
      setError(`Error: ${error.response ? error.response.status : ''} ${error.message}`);
    }
  }

  const handleConfigSubmit = async () => {
    try {
      const config = { ServerName: serverName, ApiToken: apiToken };
      const response = await axios.post('/update_config', config);
      alert(`Configuration updated: ${JSON.stringify(response.data)}`);
    } catch (error) {
      console.error('Error updating configuration:', error);
      setErrorConfig(`Error updating configuration: ${error.message}`);
    }
  };;

  return (
    <>
      <div>
	<h1>Create a New NFC Tag</h1>

        <div className="info-box">
	<span className="info-box-icon">ℹ️</span>
	  <div>
          <p><strong>Translation</strong>: Define a primary phrase and define the languages to translate it into. The server will automatically translate the phrase for you.</p>
          <p><strong>Localization</strong>: Allows you to specifically define the phrase for each language. Use this if the translation option is not correctly translating your phrase to other languages</p>
	  </div>
        </div>
	<h2>Select a Tag Type</h2>
        <button onClick={() => setFormType('localization')}>Localization</button>
        <button onClick={() => setFormType('translation')}>Translation</button>

        <h3>{formType === 'localization' ? 'Localization' : 'Translation'}</h3>

        {formType === 'localization' && localizations.map((localization, index) => (
          <div key={index}>
            <select value={localization.language} onChange={(e) => handleLocalizationChange(index, 'language', e.target.value)}>
              <option value="">Select Language</option>
              {languageCodes.map(lang => <option key={lang.code} value={lang.code}>{lang.name}</option>)}
            </select>
            <input type="text" value={localization.value} onChange={(e) => handleLocalizationChange(index, 'value', e.target.value)} placeholder="Localized Phrase"/>
          </div>
        ))}

        {formType === 'translation' && (
          <div>
            <select value={language} onChange={(e) => handleInputChange(e, 'language')}>
              <option value="">Primary Language</option>
              {languageCodes.map(lang => <option key={lang.code} value={lang.code}>{lang.name}</option>)}
            </select>
            <input type="text" value={text} onChange={(e) => handleInputChange(e, 'text')} placeholder="Primary Phrase" />
            {translations.map((translation, index) => (
              <div><select key={index} value={translation} onChange={(e) => handleTranslationChange(index, e.target.value)}>
                <option value="">Select Translation</option>
                {languageCodes.map(lang => <option key={lang.code} value={lang.code}>{lang.name}</option>)}
              </select></div>
            ))}
          </div>
        )}

      <div className="addLanguage">
        <button onClick={addLocalizationOrTranslation}>Add {formType === 'localization' ? 'Localization' : 'Translation'}</button>
      </div>
      <div>
        <button onClick={performHttpRequest}>Test Audio</button>
        <button onClick={handleWriteNFC}>Write to NFC Tag</button>
        {error && <div className="error-message">{error}</div>}
        {audio && <div><audio className="audioPlayer" controls src={audio} /></div>}
      </div>
      {jsonDisplay && (
        <div>
          <h3>JSON Output:</h3>
          <p>{jsonDisplay}</p>
        </div>
      )}

      </div>


      <div className="config-form">
        <button onClick={() => setShowConfig(!showConfig)}>
          {showConfig ? 'Hide Configuration' : 'Show Configuration'}
        </button>
      
        {showConfig && (
          <div>
            <h1>Update Configuration</h1>
            <div className="info-box">Do not change this section unless you know what you're doing</div>
            
            <div className="input-group">
              <label htmlFor="serverName">Server Name:</label>
              <input
                id="serverName"
                type="text"
                value={serverName}
                onChange={(e) => setServerName(e.target.value)}
                placeholder="Server URL"
              />
            </div>
      
            <div className="input-group">
              <label htmlFor="apiToken">API Token:</label>
              <input
                id="apiToken"
                type="text"
                value={apiToken}
                onChange={(e) => setApiToken(e.target.value)}
                placeholder="API Token"
              />
            </div>
      
            <div><button onClick={handleConfigSubmit}>Update Config</button></div>
            {errorConfig && <div className="error-message">{errorConfig}</div>}
          </div>
        )}
      </div>

    </>
  );
}

export default App;

