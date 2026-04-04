'use client';

import { useEffect, useState } from 'react';
import { getWeights, updateWeights, updateThreshold, getSchedule, updateSchedule } from '@/lib/api';
import { Save, Clock, Award, Zap } from 'lucide-react';

export default function ConfigPage() {
  const [weights, setWeights] = useState({
    watch_activity: 40, rarity: 20,
    request_accountability: 15, size_efficiency: 15, cultural_value: 10,
  });
  const [threshold, setThreshold] = useState(30);
  const [classicAge, setClassicAge] = useState(20);
  const [classicBonus, setClassicBonus] = useState(5);
  const [recentAge, setRecentAge] = useState(2);
  const [recentBonus, setRecentBonus] = useState(5);
  const [cron, setCron] = useState('0 3 * * 0');
  const [nextRun, setNextRun] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [w, s] = await Promise.all([getWeights(), getSchedule()]);
        setWeights({
          watch_activity: w.watch_activity, rarity: w.rarity,
          request_accountability: w.request_accountability,
          size_efficiency: w.size_efficiency, cultural_value: w.cultural_value,
        });
        setThreshold(w.candidate_threshold);
        setClassicAge(w.classic_age_threshold ?? 20);
        setClassicBonus(w.classic_bonus_points ?? 5);
        setRecentAge(w.recent_age_threshold ?? 2);
        setRecentBonus(w.recent_bonus_points ?? 5);
        setCron(s.cron_expression || '0 3 * * 0');
        setNextRun(s.next_run);
      } catch (e) { console.error(e); }
      setLoading(false);
    })();
  }, []);

  const total = Object.values(weights).reduce((s, v) => s + v, 0);
  const isValid = Math.abs(total - 100) < 0.01;

  const handleSlider = (key: string, val: number) => {
    setWeights(prev => ({ ...prev, [key]: val }));
    setMessage('');
  };

  const handleSave = async () => {
    if (!isValid) { setMessage('Weights must sum to 100'); return; }
    setSaving(true);
    try {
      await updateWeights({
        ...weights,
        classic_age_threshold: classicAge, classic_bonus_points: classicBonus,
        recent_age_threshold: recentAge, recent_bonus_points: recentBonus,
      });
      await updateThreshold(threshold);
      setMessage('Configuration saved!');
    } catch (e: any) { setMessage(e.message || 'Save failed'); }
    setSaving(false);
  };

  const handleScheduleSave = async () => {
    try {
      const result = await updateSchedule(cron);
      setNextRun(result.next_run);
      setMessage('Schedule updated!');
    } catch (e: any) { setMessage(e.message || 'Invalid cron'); }
  };

  const sliderData = [
    { key: 'watch_activity', label: 'Watch Activity', color: 'var(--accent-teal)' },
    { key: 'rarity', label: 'Rarity & Replaceability', color: 'var(--accent-blue)' },
    { key: 'request_accountability', label: 'Request Accountability', color: 'var(--accent-amber)' },
    { key: 'size_efficiency', label: 'Size Efficiency', color: 'var(--score-mid)' },
    { key: 'cultural_value', label: 'Cultural Value', color: 'var(--accent-slate)' },
  ];

  if (loading) return <div style={{ padding: 40, color: 'var(--text-secondary)' }}>Loading configuration...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 28, fontWeight: 800, marginBottom: 24 }}>Configuration</h1>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Scoring Weights */}
        <div className="card">
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>Scoring Weights</h2>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              Total: <span style={{ color: isValid ? 'var(--accent-teal)' : 'var(--accent-red)', fontWeight: 700 }}>
                {total.toFixed(0)}%
              </span>
            </span>
            {!isValid && <span style={{ fontSize: 12, color: 'var(--accent-red)' }}>Must equal 100%</span>}
          </div>

          {sliderData.map(({ key, label, color }) => (
            <div key={key} style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <label style={{ fontSize: 13, fontWeight: 500 }}>{label}</label>
                <span style={{ fontSize: 13, fontWeight: 700, color }}>{(weights as any)[key]}%</span>
              </div>
              <input
                type="range" min={0} max={100} step={5}
                value={(weights as any)[key]}
                onChange={e => handleSlider(key, Number(e.target.value))}
                style={{ width: '100%', accentColor: color }}
              />
            </div>
          ))}

          <div style={{ marginTop: 20 }}>
            <label style={{ fontSize: 13, fontWeight: 500 }}>Candidate Threshold</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
              <input
                type="range" min={0} max={100} step={5} value={threshold}
                onChange={e => setThreshold(Number(e.target.value))}
                style={{ flex: 1, accentColor: 'var(--accent-red)' }}
              />
              <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--accent-red)', minWidth: 40 }}>{threshold}</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
              Titles scoring below this are flagged as removal candidates
            </div>
          </div>

          <button className="btn btn-primary" onClick={handleSave} disabled={saving || !isValid} style={{ marginTop: 20 }}>
            <Save size={16} /> {saving ? 'Saving...' : 'Save Weights'}
          </button>
        </div>

        {/* Schedule */}
        <div className="card">
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>
            <Clock size={18} style={{ display: 'inline', marginRight: 8, verticalAlign: 'middle' }} />
            Scoring Schedule
          </h2>
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 13, fontWeight: 500 }}>Cron Expression</label>
            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              <input
                type="text" value={cron} onChange={e => setCron(e.target.value)}
                className="filter-select" style={{ flex: 1, padding: '8px 12px' }}
              />
              <button className="btn" onClick={handleScheduleSave}>Update</button>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
              Format: minute hour day month day_of_week
            </div>
          </div>
          {nextRun && (
            <div style={{ marginTop: 12 }}>
              <div className="stat-label">Next Scheduled Run</div>
              <div style={{ fontSize: 16, fontWeight: 600, marginTop: 4, color: 'var(--accent-teal)' }}>
                {new Date(nextRun).toLocaleString()}
              </div>
            </div>
          )}

          <div style={{ marginTop: 24, padding: 16, background: 'var(--bg-input)', borderRadius: 8 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>Common Schedules</div>
            {[
              { label: 'Weekly (Sun 3am)', value: '0 3 * * 0' },
              { label: 'Daily (3am)', value: '0 3 * * *' },
              { label: 'Twice weekly (Wed+Sun)', value: '0 3 * * 0,3' },
              { label: 'Monthly (1st, 3am)', value: '0 3 1 * *' },
            ].map(preset => (
              <button key={preset.value} className="btn btn-sm"
                style={{ marginRight: 6, marginBottom: 6 }}
                onClick={() => { setCron(preset.value); }}>
                {preset.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Classic Title Bonus */}
      <div className="card" style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>
          <Award size={18} style={{ display: 'inline', marginRight: 8, verticalAlign: 'middle', color: 'var(--accent-amber)' }} />
          Classic Title Bonus
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 20 }}>
          Titles older than <span style={{ color: 'var(--accent-amber)', fontWeight: 700 }}>{classicAge} years</span> receive
          a <span style={{ color: 'var(--accent-teal)', fontWeight: 700 }}>+{classicBonus} point</span> bonus to their keep score.
          {classicBonus === 0 && <span style={{ fontStyle: 'italic', marginLeft: 4 }}>(disabled)</span>}
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <label style={{ fontSize: 13, fontWeight: 500 }}>Age Threshold</label>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-amber)' }}>{classicAge} years</span>
            </div>
            <input
              type="range" min={15} max={30} step={5}
              value={classicAge}
              onChange={e => { setClassicAge(Number(e.target.value)); setMessage(''); }}
              style={{ width: '100%', accentColor: 'var(--accent-amber)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
              <span>15 yr</span><span>20 yr</span><span>25 yr</span><span>30 yr</span>
            </div>
          </div>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <label style={{ fontSize: 13, fontWeight: 500 }}>Bonus Points</label>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-teal)' }}>+{classicBonus}</span>
            </div>
            <input
              type="range" min={0} max={10} step={1}
              value={classicBonus}
              onChange={e => { setClassicBonus(Number(e.target.value)); setMessage(''); }}
              style={{ width: '100%', accentColor: 'var(--accent-teal)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
              <span>0 (off)</span><span>5</span><span>10</span>
            </div>
          </div>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 12 }}>
          Applied as a flat boost after the weighted score is calculated. Saved with the weights above.
        </div>
      </div>

      {/* Recent Title Bonus */}
      <div className="card" style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>
          <Zap size={18} style={{ display: 'inline', marginRight: 8, verticalAlign: 'middle', color: 'var(--accent-blue)' }} />
          Recent Title Bonus
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 20 }}>
          Titles newer than <span style={{ color: 'var(--accent-blue)', fontWeight: 700 }}>{recentAge} year{recentAge !== 1 ? 's' : ''}</span> receive
          a <span style={{ color: 'var(--accent-teal)', fontWeight: 700 }}>+{recentBonus} point</span> bonus to their keep score.
          {recentBonus === 0 && <span style={{ fontStyle: 'italic', marginLeft: 4 }}>(disabled)</span>}
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <label style={{ fontSize: 13, fontWeight: 500 }}>Age Threshold</label>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-blue)' }}>{recentAge} year{recentAge !== 1 ? 's' : ''}</span>
            </div>
            <input
              type="range" min={1} max={5} step={1}
              value={recentAge}
              onChange={e => { setRecentAge(Number(e.target.value)); setMessage(''); }}
              style={{ width: '100%', accentColor: 'var(--accent-blue)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
              <span>1 yr</span><span>2 yr</span><span>3 yr</span><span>4 yr</span><span>5 yr</span>
            </div>
          </div>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <label style={{ fontSize: 13, fontWeight: 500 }}>Bonus Points</label>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-teal)' }}>+{recentBonus}</span>
            </div>
            <input
              type="range" min={0} max={10} step={1}
              value={recentBonus}
              onChange={e => { setRecentBonus(Number(e.target.value)); setMessage(''); }}
              style={{ width: '100%', accentColor: 'var(--accent-teal)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
              <span>0 (off)</span><span>5</span><span>10</span>
            </div>
          </div>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 12 }}>
          Protects new additions from being flagged before they have time to accumulate watch activity. Saved with the weights above.
        </div>
      </div>

      {message && (
        <div style={{ marginTop: 16, padding: 12, borderRadius: 8, background: 'var(--bg-elevated)', fontSize: 14, color: 'var(--accent-teal)' }}>
          {message}
        </div>
      )}
    </div>
  );
}
