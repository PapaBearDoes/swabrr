'use client';

import { useEffect, useState, useCallback } from 'react';
import { getScores, getSummary, triggerScoring, getStatus } from '@/lib/api';
import { formatBytes, formatScore, scoreColor, timeAgo } from '@/lib/utils';
import { Play, RefreshCw, ChevronUp, ChevronDown } from 'lucide-react';

type SortField = 'keep_score' | 'file_size' | 'title' | 'last_watched';

export default function DashboardPage() {
  const [scores, setScores] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [mediaType, setMediaType] = useState<string>('');
  const [sortBy, setSortBy] = useState<SortField>('keep_score');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [loading, setLoading] = useState(true);
  const [scoring, setScoring] = useState(false);
  const perPage = 50;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page), per_page: String(perPage),
        sort_by: sortBy, sort_order: sortOrder,
      });
      if (mediaType) params.set('media_type', mediaType);
      const [scoreData, summaryData] = await Promise.all([
        getScores(params.toString()),
        getSummary(),
      ]);
      setScores(scoreData.scores || []);
      setTotal(scoreData.total || 0);
      setSummary(summaryData);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [page, sortBy, sortOrder, mediaType]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortOrder(o => o === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder(field === 'title' ? 'asc' : 'asc');
    }
    setPage(1);
  };

  const handleTriggerScore = async () => {
    setScoring(true);
    try {
      await triggerScoring();
      // Poll status until complete
      const poll = setInterval(async () => {
        const status = await getStatus();
        if (!status.running) {
          clearInterval(poll);
          setScoring(false);
          fetchData();
        }
      }, 3000);
    } catch (e) { console.error(e); setScoring(false); }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortBy !== field) return null;
    return sortOrder === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />;
  };

  const totalPages = Math.ceil(total / perPage);
  const reclaimTarget = 7.5 * 1024 ** 4; // 7.5 TB in bytes
  const reclaimed = summary?.total_removed_bytes || 0;
  const reclaimPct = Math.min((reclaimed / reclaimTarget) * 100, 100);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800 }}>Library Scores</h1>
        <button className="btn btn-primary" onClick={handleTriggerScore} disabled={scoring}>
          {scoring ? <><RefreshCw size={16} className="animate-spin" /> Scoring...</> : <><Play size={16} /> Run Scoring</>}
        </button>
      </div>

      {summary?.has_scores && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Titles Scored</div>
            <div className="stat-value">{summary.titles_scored}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Candidates</div>
            <div className="stat-value" style={{ color: 'var(--score-low)' }}>{summary.candidates_flagged}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Reclaimable</div>
            <div className="stat-value" style={{ color: 'var(--accent-amber)' }}>{formatBytes(summary.space_reclaimable_bytes)}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Space Reclaimed</div>
            <div className="stat-value" style={{ color: 'var(--accent-teal)' }}>{formatBytes(reclaimed)}</div>
            <div className="progress-bar"><div className="progress-fill" style={{ width: `${reclaimPct}%` }} /></div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>Target: 7.5 TB</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Last Run</div>
            <div style={{ fontSize: 16, fontWeight: 600, marginTop: 4 }}>{timeAgo(summary.last_run_at)}</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{summary.last_run_trigger}</div>
          </div>
        </div>
      )}

      <div className="filters">
        <select className="filter-select" value={mediaType} onChange={e => { setMediaType(e.target.value); setPage(1); }}>
          <option value="">All Types</option>
          <option value="movie">Movies</option>
          <option value="series">TV Series</option>
        </select>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{total} titles</span>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th onClick={() => handleSort('title')}>Title <SortIcon field="title" /></th>
              <th>Type</th>
              <th onClick={() => handleSort('keep_score')}>Score <SortIcon field="keep_score" /></th>
              <th>Rarity</th>
              <th>Cultural</th>
              <th onClick={() => handleSort('file_size')}>Size <SortIcon field="file_size" /></th>
              <th>Plays</th>
              <th>Viewers</th>
              <th onClick={() => handleSort('last_watched')}>Last Watched <SortIcon field="last_watched" /></th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={10} style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>Loading...</td></tr>
            ) : scores.length === 0 ? (
              <tr><td colSpan={10} style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>No scores yet. Run a scoring cycle to get started.</td></tr>
            ) : scores.map((s: any) => (
              <tr key={s.tmdb_id}>
                <td>
                  <div style={{ fontWeight: 600 }}>{s.title}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{s.year}</div>
                </td>
                <td><span style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>{s.media_type}</span></td>
                <td>
                  <span className={`score-badge ${s.keep_score >= 70 ? 'score-high' : s.keep_score >= 30 ? 'score-mid' : 'score-low'}`}>
                    {formatScore(s.keep_score)}
                  </span>
                </td>
                <td><span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{formatScore(s.rarity_score)}</span></td>
                <td><span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{formatScore(s.cultural_value_score)}</span></td>
                <td>{formatBytes(s.file_size_bytes)}</td>
                <td>{s.total_plays || 0}</td>
                <td>{s.unique_viewers || 0}</td>
                <td style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{timeAgo(s.last_watched_at)}</td>
                <td>
                  {s.is_protected && <span style={{ color: 'var(--accent-blue)', fontSize: 12 }}>🛡 Protected</span>}
                  {s.is_candidate && !s.is_protected && <span style={{ color: 'var(--score-low)', fontSize: 12 }}>⚠ Candidate</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 20 }}>
          <button className="btn btn-sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>Prev</button>
          <span style={{ padding: '4px 12px', fontSize: 13, color: 'var(--text-secondary)' }}>Page {page} of {totalPages}</span>
          <button className="btn btn-sm" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>Next</button>
        </div>
      )}
    </div>
  );
}
