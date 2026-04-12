import { useState } from 'react'
import './App.css'

function App() {
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) return

    setLoading(true)
    setError(null)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('http://localhost:8000/proofread', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'エラーが発生しました')
      }
      const data = await res.json()
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <h1>AI校正アプリ</h1>
      <p className="subtitle">PDFをアップロードして、AIが本文を校正します</p>

      <form onSubmit={handleSubmit} className="upload-form">
        <label className="file-label">
          <input
            type="file"
            accept=".pdf"
            onChange={(e) => setFile(e.target.files[0])}
            className="file-input"
          />
          <span className="file-button">
            {file ? file.name : 'PDFファイルを選択'}
          </span>
        </label>
        <button type="submit" disabled={!file || loading} className="submit-button">
          {loading ? '校正中...' : '校正する'}
        </button>
      </form>

      {loading && (
        <div className="loading">
          <div className="spinner" />
          <p>AIが校正しています。しばらくお待ちください...</p>
        </div>
      )}

      {error && <div className="error">{error}</div>}

      {result && (
        <div className="result">
          <h2>校正結果: {result.filename}</h2>
          <div className="result-content">{result.result}</div>
        </div>
      )}
    </div>
  )
}

export default App
