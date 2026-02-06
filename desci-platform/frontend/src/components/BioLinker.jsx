/**
 * BioLinker Dashboard Component
 * 정부 과제 적합도 분석 대시보드
 */
import { useState } from 'react';
import client from '../api/client';

// 등급별 색상
const gradeColors = {
    S: 'bg-gradient-to-r from-yellow-400 to-orange-500',
    A: 'bg-gradient-to-r from-green-400 to-emerald-500',
    B: 'bg-gradient-to-r from-blue-400 to-cyan-500',
    C: 'bg-gradient-to-r from-gray-400 to-slate-500',
    D: 'bg-gradient-to-r from-red-400 to-rose-500',
};

const gradeLabels = {
    S: '즉시 지원 추천 🔥',
    A: '높은 적합도 ✅',
    B: '전략적 판단 필요 ⚖️',
    C: '지원 비추천 ⚠️',
    D: '관련 없음 ❌',
};

export default function BioLinker() {
    const [rfpText, setRfpText] = useState('');
    const [profile, setProfile] = useState({
        company_name: '',
        tech_keywords: '',
        tech_description: '',
        company_size: '벤처기업',
        current_trl: 'TRL 4',
    });
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleAnalyze = async () => {
        if (!rfpText.trim() || !profile.company_name || !profile.tech_keywords) {
            setError('공고문, 회사명, 보유 기술을 입력해주세요.');
            return;
        }

        setLoading(true);
        setError('');

        try {
            const response = await client.post('http://localhost:8001/analyze', {
                rfp_text: rfpText,
                user_profile: {
                    company_name: profile.company_name,
                    tech_keywords: profile.tech_keywords.split(',').map(k => k.trim()),
                    tech_description: profile.tech_description,
                    company_size: profile.company_size,
                    current_trl: profile.current_trl,
                },
            });
            setResult(response.data);
        } catch (err) {
            setError('분석 중 오류가 발생했습니다. BioLinker 서버가 실행 중인지 확인해주세요.');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const loadDemo = async () => {
        setLoading(true);
        try {
            const response = await client.get('http://localhost:8001/demo');
            setResult(response.data);
            setRfpText(response.data.rfp.body_text);
            setProfile({
                company_name: '데모 바이오텍',
                tech_keywords: '항체, 신약, AI, 임상',
                tech_description: 'AI 기반 항체 신약 개발 전문 기업',
                company_size: '벤처기업',
                current_trl: 'TRL 4',
            });
        } catch (err) {
            setError('데모 로딩 실패. BioLinker 서버 확인 필요.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div className="flex items-center gap-4">
                        <span className="text-4xl">🧬</span>
                        <div>
                            <h1 className="text-3xl font-bold text-white">BioLinker</h1>
                            <p className="text-gray-400">AI 바이오 과제 매칭 에이전트</p>
                        </div>
                    </div>
                    <button
                        onClick={loadDemo}
                        className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
                    >
                        🎯 데모 보기
                    </button>
                </div>

                <div className="grid lg:grid-cols-2 gap-6">
                    {/* Input Section */}
                    <div className="space-y-6">
                        {/* Company Profile */}
                        <div className="bg-white/5 backdrop-blur border border-white/10 rounded-xl p-6">
                            <h2 className="text-xl font-semibold text-white mb-4">🏢 회사 프로필</h2>
                            <div className="space-y-4">
                                <input
                                    type="text"
                                    placeholder="회사명"
                                    value={profile.company_name}
                                    onChange={(e) => setProfile({ ...profile, company_name: e.target.value })}
                                    className="w-full bg-white/10 border border-white/20 text-white px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-cyan-400"
                                />
                                <input
                                    type="text"
                                    placeholder="보유 기술 (쉼표로 구분: 항체, 신약, AI)"
                                    value={profile.tech_keywords}
                                    onChange={(e) => setProfile({ ...profile, tech_keywords: e.target.value })}
                                    className="w-full bg-white/10 border border-white/20 text-white px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-cyan-400"
                                />
                                <textarea
                                    placeholder="회사 역량 설명"
                                    value={profile.tech_description}
                                    onChange={(e) => setProfile({ ...profile, tech_description: e.target.value })}
                                    rows={2}
                                    className="w-full bg-white/10 border border-white/20 text-white px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-cyan-400"
                                />
                                <div className="grid grid-cols-2 gap-4">
                                    <select
                                        value={profile.company_size}
                                        onChange={(e) => setProfile({ ...profile, company_size: e.target.value })}
                                        className="bg-white/10 border border-white/20 text-white px-4 py-3 rounded-lg"
                                    >
                                        <option value="벤처기업">벤처기업</option>
                                        <option value="중소기업">중소기업</option>
                                        <option value="중견기업">중견기업</option>
                                        <option value="대기업">대기업</option>
                                    </select>
                                    <select
                                        value={profile.current_trl}
                                        onChange={(e) => setProfile({ ...profile, current_trl: e.target.value })}
                                        className="bg-white/10 border border-white/20 text-white px-4 py-3 rounded-lg"
                                    >
                                        {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => (
                                            <option key={n} value={`TRL ${n}`}>TRL {n}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                        </div>

                        {/* RFP Input */}
                        <div className="bg-white/5 backdrop-blur border border-white/10 rounded-xl p-6">
                            <h2 className="text-xl font-semibold text-white mb-4">📄 공고문 입력</h2>
                            <textarea
                                placeholder="정부 과제 공고문을 복사해서 붙여넣으세요..."
                                value={rfpText}
                                onChange={(e) => setRfpText(e.target.value)}
                                rows={8}
                                className="w-full bg-white/10 border border-white/20 text-white px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-cyan-400"
                            />

                            {error && (
                                <div className="mt-4 p-3 bg-red-500/20 border border-red-500/50 text-red-300 rounded-lg">
                                    ⚠️ {error}
                                </div>
                            )}

                            <button
                                onClick={handleAnalyze}
                                disabled={loading}
                                className="mt-4 w-full py-4 bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-semibold rounded-lg hover:opacity-90 transition-all disabled:opacity-50"
                            >
                                {loading ? '분석 중... ⏳' : '🔍 적합도 분석하기'}
                            </button>
                        </div>
                    </div>

                    {/* Results Section */}
                    <div className="space-y-6">
                        {result ? (
                            <>
                                {/* Score Card */}
                                <div className={`${gradeColors[result.result.fit_grade]} rounded-xl p-6 text-white`}>
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-white/80 text-sm">적합도 점수</p>
                                            <p className="text-5xl font-bold">{result.result.fit_score}점</p>
                                        </div>
                                        <div className="text-right">
                                            <p className="text-6xl font-bold">{result.result.fit_grade}</p>
                                            <p className="text-white/80">{gradeLabels[result.result.fit_grade]}</p>
                                        </div>
                                    </div>
                                </div>

                                {/* RFP Info */}
                                <div className="bg-white/5 backdrop-blur border border-white/10 rounded-xl p-6">
                                    <h3 className="text-lg font-semibold text-white mb-3">📋 공고 정보</h3>
                                    <div className="space-y-2 text-gray-300">
                                        <p><span className="text-gray-500">제목:</span> {result.rfp.title}</p>
                                        <p><span className="text-gray-500">출처:</span> {result.rfp.source}</p>
                                        <p><span className="text-gray-500">키워드:</span> {result.rfp.keywords.join(', ')}</p>
                                    </div>
                                </div>

                                {/* Match Summary */}
                                <div className="bg-white/5 backdrop-blur border border-white/10 rounded-xl p-6">
                                    <h3 className="text-lg font-semibold text-white mb-3">✅ 매칭 근거</h3>
                                    <ul className="space-y-2">
                                        {result.result.match_summary.map((item, i) => (
                                            <li key={i} className="flex items-start gap-2 text-gray-300">
                                                <span className="text-green-400">•</span>
                                                {item}
                                            </li>
                                        ))}
                                    </ul>
                                </div>

                                {/* Risk Flags */}
                                {result.result.risk_flags.length > 0 && (
                                    <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6">
                                        <h3 className="text-lg font-semibold text-red-400 mb-3">⚠️ 리스크</h3>
                                        <ul className="space-y-2">
                                            {result.result.risk_flags.map((item, i) => (
                                                <li key={i} className="text-red-300">• {item}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {/* Recommended Actions */}
                                <div className="bg-cyan-500/10 border border-cyan-500/30 rounded-xl p-6">
                                    <h3 className="text-lg font-semibold text-cyan-400 mb-3">🎯 추천 액션</h3>
                                    <ul className="space-y-2">
                                        {result.result.recommended_actions.map((item, i) => (
                                            <li key={i} className="text-cyan-300">• {item}</li>
                                        ))}
                                    </ul>
                                </div>
                            </>
                        ) : (
                            <div className="bg-white/5 backdrop-blur border border-white/10 rounded-xl p-12 text-center">
                                <span className="text-6xl">🔍</span>
                                <p className="text-gray-400 mt-4">
                                    공고문을 입력하고 분석 버튼을 클릭하세요
                                </p>
                                <p className="text-gray-500 text-sm mt-2">
                                    또는 데모 보기를 눌러 샘플 결과를 확인하세요
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
