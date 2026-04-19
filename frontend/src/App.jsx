import { useState } from 'react'
import './App.css'

const CATEGORY_LABEL = {
  typo: '誤字脱字',
  notation: '表記ゆれ',
  grammar: '文法',
}

const SEVERITY_LABEL = {
  high: '高',
  medium: '中',
  low: '低',
}

function App() {
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [severityFilter, setSeverityFilter] = useState('all')

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

  const filteredCorrections = result?.corrections.filter((c) => {
    if (severityFilter === 'all') return true
    return c.severity === severityFilter
  }) ?? []

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
          <p>AIが校正しています。大きいPDFは数分かかる場合があります...</p>
        </div>
      )}

      {error && <div className="error">{error}</div>}

      {result && (
        <div className="result">
          <div className="result-header">
            <h2>校正結果: {result.filename}</h2>
            <div className="summary">
              <span className="total">計 {result.total_corrections} 件の指摘</span>
              <span className="badge high">高 {result.summary.high}</span>
              <span className="badge medium">中 {result.summary.medium}</span>
              <span className="badge low">低 {result.summary.low}</span>
              {result.total_chunks > 1 && (
                <span className="chunk-info">（{result.total_chunks}分割処理）</span>
              )}
            </div>

            <div className="filter-bar">
              <button
                className={severityFilter === 'all' ? 'active' : ''}
                onClick={() => setSeverityFilter('all')}
              >
                すべて
              </button>
              <button
                className={severityFilter === 'high' ? 'active' : ''}
                onClick={() => setSeverityFilter('high')}
              >
                高のみ
              </button>
              <button
                className={severityFilter === 'medium' ? 'active' : ''}
                onClick={() => setSeverityFilter('medium')}
              >
                中のみ
              </button>
              <button
                className={severityFilter === 'low' ? 'active' : ''}
                onClick={() => setSeverityFilter('low')}
              >
                低のみ
              </button>
            </div>
          </div>

          {filteredCorrections.length === 0 ? (
            <p className="empty">該当する指摘はありません</p>
          ) : (
            <div className="corrections">
              {filteredCorrections.map((c) => (
                <div key={c.id} className="correction-card">
                  <div className="card-header">
                    <span className={`card-category ${c.category}`}>
                      {CATEGORY_LABEL[c.category] ?? c.category}
                    </span>
                    <span className={`card-severity ${c.severity}`}>
                      {SEVERITY_LABEL[c.severity] ?? c.severity}
                    </span>
                    <span className="card-page">p.{c.page}</span>
                  </div>
                  <div className="card-diff">
                    <span className="original">{c.original}</span>
                    <span className="arrow">→</span>
                    <span className="suggestion">{c.suggestion}</span>
                  </div>
                  {c.explanation && (
                    <p className="card-explanation">{c.explanation}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
