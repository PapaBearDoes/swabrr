'use client';

import { useEffect, useState, useCallback } from 'react';
import { getCandidates, markRemoved, batchMarkRemoved, exportCandidatesCSV, protectTitle } from '@/lib/api';
import { formatBytes, formatScore } from '@/lib/utils';
import { Trash2, CheckCircle, Download, Shield } from 'lucide-react';

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [mediaType, setMediaType] = useState('');
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState<number | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [batchRemoving, setBatchRemoving] = useState(false);
  const [protecting, setProtecting] = useState<number | null>(null);
  const perPage = 50;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page), per_page: String(perPage),
        sort_by: 'keep_score', sort_order: 'asc',
      });
      if (mediaType) params.set('media_type', mediaType);
      const data = await getCandidates(params.toString());
      setCandidates(data.scores || []);
      setTotal(data.total || 0);
      setSelected(new Set());
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [page, mediaType]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleRemove = async (tmdbId: number) => {
    if (!confirm('Mark this title as removed? (Make sure you\'ve deleted it in Radarr/Sonarr first)')) return;
    setRemoving(tmdbId);
    try {
      await markRemoved(tmdbId);
      setCandidates(prev => prev.filter(c => c.tmdb_id !== tmdbId));
      setTotal(prev => prev - 1);
      setSelected(prev => { const s = new Set(prev); s.delete(tmdbId); return s; });
    } catch (e) { console.error(e); }
    setRemoving(null);
  };

  const handleBatchRemove = async () => {
    if (selected.size === 0) return;
    if (!confirm(`Mark ${selected.size} titles as removed? (Make sure you've deleted them in Radarr/Sonarr first)`)) return;
    setBatchRemoving(true);
    try {
      await batchMarkRemoved(Array.from(selected));
      setCandidates(prev => prev.filter(c => !selected.has(c.tmdb_id)));
      setTotal(prev => prev - selected.size);
      setSelected(new Set());
    } catch (e) { console.error(e); }
    setBatchRemoving(false);
  };

  const handleProtect = async (tmdbId: number, title: string) => {
    const reason = prompt(`Protect "${title}"?\n\nOptional: enter a reason (or leave blank):`);
    if (reason === null) return; // User cancelled
    setProtecting(tmdbId);
    try {
      await protectTitle(tmdbId, reason || undefined);
      // Remove from candidates list since it's now protected
      setCandidates(prev => prev.filter(c => c.tmdb_id !== tmdbId));
      setTotal(prev => prev - 1);
      setSelected(prev => { const s = new Set(prev); s.delete(tmdbId); return s; });
    } catch (e) { console.error(e); }
    setProtecting(null);
  };

  const toggleSelect = (tmdbId: number) => {
    setSelected(prev => {
      const s = new Set(prev);
      if (s.has(tmdbId)) s.delete(tmdbId); else s.add(tmdbId);
      return s;
    });
  };

  const toggleAll = () => {
    if (selected.size === candidates.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(candidates.map(c => c.tmdb_id)));
    }
  };

  const totalSize = candidates.reduce((sum, c) => sum + (c.file_size_bytes || 0), 0);
  const selectedSize = candidates.filter(c => selected.has(c.tmdb_id)).reduce((s, c) => s + (c.file_size_bytes || 0), 0);
  const totalPages = Math.ceil(total / perPage);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 800 }}>Removal Candidates</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 4 }}>
            Titles scoring below threshold. Delete in Radarr/Sonarr first, then mark as removed here.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <a href={exportCandidatesCSV()} className="btn btn-sm" download>
            <Download size={14} /> Export CSV
          </a>
          {selected.size > 0 && (
            <button className="btn btn-danger" onClick={handleBatchRemove} disabled={batchRemoving}>
              <Trash2 size={14} /> {batchRemoving ? 'Removing...' : `Remove ${selected.size} Selected (${formatBytes(selectedSize)})`}
            </button>
          )}
        </div>
      </div>

      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginTop: 16 }}>
        <div className="stat-card">
          <div className="stat-label">Candidates</div>
          <div className="stat-value" style={{ color: 'var(--score-low)' }}>{total}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Reclaimable (this page)</div>
          <div className="stat-value" style={{ color: 'var(--accent-amber)' }}>{formatBytes(totalSize)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Filter</div>
          <select className="filter-select" style={{ marginTop: 8 }} value={mediaType} onChange={e => { setMediaType(e.target.value); setPage(1); }}>
            <option value="">All Types</option>
            <option value="movie">Movies</option>
            <option value="series">TV Series</option>
          </select>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: 40 }}>
                <input type="checkbox" checked={selected.size === candidates.length && candidates.length > 0} onChange={toggleAll} />
              </th>
              <th>Title</th>
              <th>Type</th>
              <th>Score</th>
              <th>Size</th>
              <th>Rarity</th>
              <th>Cultural</th>
              <th>Watch Activity</th>
              <th>Request</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={10} style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>Loading...</td></tr>
            ) : candidates.length === 0 ? (
              <tr><td colSpan={10} style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>
                <CheckCircle size={32} style={{ marginBottom: 8, opacity: 0.5 }} /><br />No removal candidates. Your library is in good shape!
              </td></tr>
            ) : candidates.map((c: any) => (
              <tr key={c.tmdb_id} style={{ background: selected.has(c.tmdb_id) ? 'var(--bg-elevated)' : undefined }}>
                <td><input type="checkbox" checked={selected.has(c.tmdb_id)} onChange={() => toggleSelect(c.tmdb_id)} /></td>
                <td><div style={{ fontWeight: 600 }}>{c.title}</div><div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{c.year}</div></td>
                <td><span style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>{c.media_type}</span></td>
                <td><span className="score-badge score-low">{formatScore(c.keep_score)}</span></td>
                <td>{formatBytes(c.file_size_bytes)}</td>
                <td><span style={{ fontSize: 13 }}>{formatScore(c.rarity_score || 0)}</span></td>
                <td><span style={{ fontSize: 13 }}>{formatScore(c.cultural_value_score || 0)}</span></td>
                <td><span style={{ fontSize: 13 }}>{formatScore(c.watch_activity_score || 0)}</span></td>
                <td><span style={{ fontSize: 13 }}>{formatScore(c.request_score || 0)}</span></td>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button className="btn btn-sm" onClick={() => handleProtect(c.tmdb_id, c.title)} disabled={protecting === c.tmdb_id} title="Protect this title">
                      <Shield size={14} /> {protecting === c.tmdb_id ? '...' : 'Protect'}
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => handleRemove(c.tmdb_id)} disabled={removing === c.tmdb_id}>
                      <Trash2 size={14} /> {removing === c.tmdb_id ? '...' : 'Remove'}
                    </button>
                  </div>
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
