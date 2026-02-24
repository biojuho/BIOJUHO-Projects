import { ExternalLink, Mail, Phone } from 'lucide-react';

export default function Footer() {
    return (
        <footer className="mt-16 py-8 border-t border-white/[0.04] text-center text-sm text-white/25">
            <div className="flex flex-col md:flex-row justify-center items-center gap-6 mb-4">
                <div className="flex items-center gap-2">
                    <span className="font-display font-semibold text-white/50">쥬라프 (Joolife)</span>
                    <span className="hidden md:inline text-white/10">|</span>
                    <span>Representative: Park Juho</span>
                </div>
                <div className="flex items-center gap-4">
                    <a href="tel:010-3159-3708" className="flex items-center gap-1 hover:text-primary transition-colors">
                        <Phone className="w-3 h-3" /> 010-3159-3708
                    </a>
                    <a href="mailto:joolife@joolife.io.kr" className="flex items-center gap-1 hover:text-primary transition-colors">
                        <Mail className="w-3 h-3" /> joolife@joolife.io.kr
                    </a>
                    <a href="https://joolife.io.kr" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 hover:text-primary transition-colors">
                        <ExternalLink className="w-3 h-3" /> joolife.io.kr
                    </a>
                </div>
            </div>
            <p className="text-white/15 text-xs mb-2">
                Addr: 경기 안양시 동안구 관평로212번길 21 공작부영아파트 309동 1312호
            </p>
            <p className="text-white/15 text-xs">
                © {new Date().getFullYear()} Joolife. All rights reserved.
            </p>
        </footer>
    );
}
