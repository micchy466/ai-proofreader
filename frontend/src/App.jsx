import { useState, useRef, useEffect } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import './App.css'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

const PDF_OPTIONS = {
  cMapUrl: '/cmaps/',
  cMapPacked: true,
  standardFontDataUrl: '/standard_fonts/',
}

const API_BASE = 'http://localhost:8000'

const CATEGORY_LABEL = {
  typo: '誤字脱字',
  notation: '表記ゆれ',
  grammar: '文法',
}

const SEVERITY_LABEL = { high: '高', medium: '中', low: '低' }

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function App() {
  const [file, setFile] = useState(null)
  const [fileUrl, setFileUrl] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [severityFilter, setSeverityFilter] = useState('all')
  const [numPages, setNumPages] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [pageWidth, setPageWidth] = useState(700)
  const [searchText, setSearchText] = useState('')
  const [selectedCardId, setSelectedCardId] = useState(null)
  const [history, setHistory] = useState([])
  const [cacheBanner, setCacheBanner] = useState(false)

  const viewerRef = useRef(null)

  // 履歴を取得
  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/history`)
      if (res.ok) {
        const data = await res.json()
        setHistory(data)
      }
    } catch {
      // 履歴取得失敗はサイレント
    }
  }

  useEffect(() => {
    fetchHistory()
  }, [])

  // file 選択時に blob URL を作る（新規アップロード時）
  useEffect(() => {
    if (!file) return
    const url = URL.createObjectURL(file)
    setFileUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  // PDFビューアの幅調整
  useEffect(() => {
    if (!result) return
    const updateWidth = () => {
      if (viewerRef.current) {
        const width = viewerRef.current.clientWidth - 32
        if (width > 100) setPageWidth(Math.max(400, width))
      }
    }
    const timer = setTimeout(updateWidth, 100)
    window.addEventListener('resize', updateWidth)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('resize', updateWidth)
    }
  }, [result])

  // ハイライト処理
  useEffect(() => {
    if (!searchText) return
    const isIgnorable = (ch) => /\s/.test(ch)

    const applyHighlight = () => {
      const textLayer = document.querySelector('.react-pdf__Page__textContent')
      if (!textLayer) return

      textLayer.querySelectorAll('mark.pdf-highlight').forEach((m) => {
        const parent = m.parentNode
        while (m.firstChild) parent.insertBefore(m.firstChild, m)
        parent.removeChild(m)
        parent.normalize()
      })

      const walker = document.createTreeWalker(textLayer, NodeFilter.SHOW_TEXT)
      const charMap = []
      let normalizedText = ''
      let node
      while ((node = walker.nextNode())) {
        for (let i = 0; i < node.data.length; i++) {
          const ch = node.data[i]
          if (isIgnorable(ch)) continue
          charMap.push({ node, offset: i })
          normalizedText += ch
        }
      }
      if (!normalizedText) return

      const normalizedSearch = Array.from(searchText).filter((c) => !isIgnorable(c)).join('')
      if (!normalizedSearch) return

      const matches = []
      let from = 0
      while (true) {
        const idx = normalizedText.indexOf(normalizedSearch, from)
        if (idx === -1) break
        matches.push([idx, idx + normalizedSearch.length])
        from = idx + normalizedSearch.length
      }
      if (matches.length === 0) return

      for (let mi = matches.length - 1; mi >= 0; mi--) {
        const [start, end] = matches[mi]
        let i = start
        while (i < end) {
          const curNode = charMap[i].node
          let j = i
          while (j < end && charMap[j].node === curNode) j++
          const localStart = charMap[i].offset
          const localEnd = charMap[j - 1].offset + 1
          try {
            const range = document.createRange()
            range.setStart(curNode, localStart)
            range.setEnd(curNode, localEnd)
            const mark = document.createElement('mark')
            mark.className = 'pdf-highlight'
            range.surroundContents(mark)
          } catch {
            // surroundContents fails at node boundaries, skip
          }
          i = j
        }
      }
    }

    const timers = [50, 200, 500, 1000].map((d) => setTimeout(applyHighlight, d))
    return () => timers.forEach(clearTimeout)
  }, [searchText, currentPage, result])

  const handleSubmit = async (e, force = false) => {
    if (e) e.preventDefault()
    if (!file) return
    setLoading(true)
    setError(null)
    setResult(null)
    setCurrentPage(1)
    setSearchText('')
    setSelectedCardId(null)
    setCacheBanner(false)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const url = force
        ? `${API_BASE}/proofread?force=true`
        : `${API_BASE}/proofread`
      const res = await fetch(url, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'エラーが発生しました')
      }
      const data = await res.json()
      setResult(data)
      setCacheBanner(!!data.cached)
      fetchHistory()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const openHistoryResult = async (historyItem) => {
    setLoading(true)
    setError(null)
    setCacheBanner(false)
    setCurrentPage(1)
    setSearchText('')
    setSelectedCardId(null)
    try {
      const res = await fetch(`${API_BASE}/results/${historyItem.id}`)
      if (!res.ok) throw new Error('結果の取得に失敗しました')
      const data = await res.json()
      setResult(data)
      setFile(null)
      setFileUrl(`${API_BASE}/results/${historyItem.id}/pdf`)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const deleteHistoryItem = async (id, e) => {
    e.stopPropagation()
    if (!confirm('この校正結果を削除しますか？')) return
    try {
      await fetch(`${API_BASE}/results/${id}`, { method: 'DELETE' })
      fetchHistory()
      if (result?.id === id) {
        setResult(null)
        setFile(null)
        setFileUrl(null)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const handleCardClick = (card) => {
    setSelectedCardId(card.id)
    const firstPage = card.pages?.[0] ?? 1
    setCurrentPage(firstPage)
    setSearchText(card.original ?? '')
  }

  const filteredCorrections = result?.corrections.filter((c) => {
    if (severityFilter === 'all') return true
    return c.severity === severityFilter
  }) ?? []

  // アップロード画面
  if (!result && !loading) {
    return (
      <div className="app-upload">
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
          <button type="submit" disabled={!file} className="submit-button">
            校正する
          </button>
          {file && (
            <button
              type="button"
              disabled={!file}
              className="force-button"
              onClick={() => handleSubmit(null, true)}
              title="キャッシュを無視して再校正（API料金がかかります）"
            >
              再校正
            </button>
          )}
        </form>

        {error && <div className="error">{error}</div>}

        {history.length > 0 && (
          <div className="history-section">
            <h2>過去の校正結果</h2>
            <div className="history-list">
              {history.map((h) => (
                <div
                  key={h.id}
                  className="history-item"
                  onClick={() => openHistoryResult(h)}
                >
                  <div className="history-main">
                    <div className="history-filename">{h.filename}</div>
                    <div className="history-meta">
                      <span>{formatDate(h.created_at)}</span>
                      <span>・</span>
                      <span>{h.total_unique_corrections}種 / {h.total_corrections}件</span>
                      {h.summary.high > 0 && (
                        <span className="badge-mini high">高 {h.summary.high}</span>
                      )}
                      {h.summary.medium > 0 && (
                        <span className="badge-mini medium">中 {h.summary.medium}</span>
                      )}
                      {h.summary.low > 0 && (
                        <span className="badge-mini low">低 {h.summary.low}</span>
                      )}
                    </div>
                  </div>
                  <button
                    className="delete-button"
                    onClick={(e) => deleteHistoryItem(h.id, e)}
                    title="削除"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  if (loading) {
    return (
      <div className="app-upload">
        <h1>AI校正アプリ</h1>
        <div className="loading">
          <div className="spinner" />
          <p>AIが校正しています。大きいPDFは数分かかる場合があります...</p>
        </div>
      </div>
    )
  }

  // 結果表示（左右分割）
  return (
    <div className="app-split">
      <header className="split-header">
        <div className="split-header-left">
          <h1>AI校正アプリ</h1>
          <span className="filename">{result.filename}</span>
          {cacheBanner && (
            <span className="cache-badge">過去の結果を再利用しました</span>
          )}
        </div>
        <button
          className="reset-button"
          onClick={() => {
            setResult(null)
            setFile(null)
            setFileUrl(null)
            setSelectedCardId(null)
            setSearchText('')
            setCacheBanner(false)
            fetchHistory()
          }}
        >
          別のPDFを校正
        </button>
      </header>

      <div className="split-main">
        <div className="pdf-pane" ref={viewerRef}>
          <div className="pdf-toolbar">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
            >
              ←
            </button>
            <span className="page-indicator">
              {currentPage} / {numPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(numPages, p + 1))}
              disabled={currentPage >= numPages}
            >
              →
            </button>
            {searchText && (
              <span className="search-indicator">
                ハイライト中: <strong>{searchText}</strong>
                <button
                  className="clear-search"
                  onClick={() => setSearchText('')}
                >
                  ×
                </button>
              </span>
            )}
          </div>
          <div className="pdf-viewer">
            {fileUrl && (
              <Document
                file={fileUrl}
                options={PDF_OPTIONS}
                onLoadSuccess={({ numPages: n }) => setNumPages(n)}
                loading={<div className="pdf-loading">PDF読み込み中...</div>}
              >
                <Page pageNumber={currentPage} width={pageWidth} />
              </Document>
            )}
          </div>
        </div>

        <div className="correction-pane">
          <div className="correction-header">
            <div className="summary">
              <span className="total">
                {result.total_unique_corrections ?? result.corrections.length} 種の指摘
                {result.total_corrections > (result.total_unique_corrections ?? result.corrections.length) && (
                  <span className="total-detail"> / 延べ {result.total_corrections} 件</span>
                )}
              </span>
            </div>
            <div className="badges">
              <span className="badge high">高 {result.summary.high}</span>
              <span className="badge medium">中 {result.summary.medium}</span>
              <span className="badge low">低 {result.summary.low}</span>
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

          <div className="correction-list">
            {filteredCorrections.length === 0 ? (
              <p className="empty">該当する指摘はありません</p>
            ) : (
              filteredCorrections.map((c) => (
                <div
                  key={c.id}
                  className={`correction-card ${selectedCardId === c.id ? 'selected' : ''}`}
                  onClick={() => handleCardClick(c)}
                >
                  <div className="card-header">
                    <span className={`card-category ${c.category}`}>
                      {CATEGORY_LABEL[c.category] ?? c.category}
                    </span>
                    <span className={`card-severity ${c.severity}`}>
                      {SEVERITY_LABEL[c.severity] ?? c.severity}
                    </span>
                    {c.count > 1 && (
                      <span className="card-count">{c.count}件</span>
                    )}
                    <span className="card-pages">
                      {c.pages && c.pages.length > 0 && (
                        <>p.{c.pages.join(', ')}</>
                      )}
                    </span>
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
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
