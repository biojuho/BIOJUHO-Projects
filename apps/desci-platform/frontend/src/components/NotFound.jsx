import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Beaker, Sparkles } from 'lucide-react';
import { useLocale } from '../contexts/LocaleContext';

export default function NotFound() {
    const { locale } = useLocale();
    const isKo = locale === 'ko-KR';

    return (
        <div className="relative min-h-screen overflow-hidden" style={{ background: 'var(--bg-primary, #f0ece6)' }}>
            <div className="ambient-bg" aria-hidden="true" />

            <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6 text-center">
                <motion.div
                    initial={{ opacity: 0, y: 32 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6, ease: [0.2, 0.9, 0.2, 1] }}
                    className="glass-card w-full max-w-lg p-12"
                >
                    <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-[2rem] bg-gradient-to-br from-primary to-accent text-white shadow-clay-soft">
                        <Beaker className="h-10 w-10" />
                    </div>

                    <p className="clay-chip mb-4 inline-block">404</p>

                    <h1 className="font-display text-4xl font-semibold text-ink">
                        {isKo ? '페이지를 찾을 수 없습니다' : 'Page Not Found'}
                    </h1>
                    <p className="mt-4 text-base leading-7 text-ink-muted">
                        {isKo
                            ? '요청하신 페이지가 없거나 이동되었습니다. 홈으로 돌아가거나 대시보드에서 다시 시작하세요.'
                            : 'The page you requested does not exist or has moved. Return home or continue from the dashboard.'}
                    </p>

                    <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
                        <Link to="/" className="clay-button px-6 py-3 font-semibold text-ink">
                            <ArrowLeft className="h-4 w-4" />
                            {isKo ? '홈으로' : 'Go home'}
                        </Link>
                        <Link to="/dashboard" className="clay-button clay-button-primary px-6 py-3 font-semibold text-white">
                            <Sparkles className="h-4 w-4" />
                            {isKo ? '대시보드' : 'Dashboard'}
                        </Link>
                    </div>
                </motion.div>
            </div>
        </div>
    );
}
