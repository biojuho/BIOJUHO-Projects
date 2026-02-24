import { motion, AnimatePresence } from 'framer-motion'; // eslint-disable-line no-unused-vars

const Terms = ({ isOpen, onClose }) => {
    if (!isOpen) return null;

    return (
        <AnimatePresence>
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    className="bg-surface-raised border border-white/[0.08] rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col"
                    style={{ boxShadow: '0 32px 64px rgba(0,0,0,0.6)' }}
                >
                    {/* Header */}
                    <div className="p-6 border-b border-white/[0.06] flex justify-between items-center bg-white/[0.02] rounded-t-2xl">
                        <h2 className="font-display text-lg font-bold text-white">📜 이용약관 및 개인정보 처리방침</h2>
                        <button
                            onClick={onClose}
                            className="text-white/30 hover:text-white transition-colors p-1"
                        >
                            ✕
                        </button>
                    </div>

                    {/* Content */}
                    <div className="flex-1 overflow-y-auto p-6 space-y-6 text-white/60 leading-relaxed">
                        <div className="bg-highlight/[0.06] border border-highlight/15 rounded-xl p-4 mb-6">
                            <h3 className="text-highlight font-bold flex items-center gap-2 mb-2">
                                ⚠️ AI 서비스 면책 조항 (필독)
                            </h3>
                            <p className="text-highlight/70 text-sm">
                                본 서비스에서 제공하는 AI 분석 및 매칭 결과는 참고용이며, 정확성을 100% 보장하지 않습니다.
                                **BioLinker AI**의 분석 결과에 따른 연구 제안서 작성, 펀딩 지원 등의 최종 책임은 사용자에게 있으며,
                                회사는 이에 대한 법적 책임을 지지 않습니다.
                            </p>
                        </div>

                        <section>
                            <h3 className="font-display text-base font-bold text-white mb-2 flex items-center gap-2">
                                <span className="w-1 h-5 bg-primary rounded-full"></span>
                                제1조 (목적)
                            </h3>
                            <p className="pl-3 border-l-2 border-white/[0.04]">본 약관은 Desci Platform(이하 "회사")이 제공하는 서비스의 이용조건 및 절차, 회사와 회원의 권리, 의무 및 책임사항을 규정함을 목적으로 합니다.</p>
                        </section>

                        <section>
                            <h3 className="font-display text-base font-bold text-white mb-2 flex items-center gap-2">
                                <span className="w-1 h-5 bg-accent rounded-full"></span>
                                제2조 (저작권의 귀속 및 책임)
                            </h3>
                            <ul className="list-disc pl-8 space-y-2 border-l-2 border-white/[0.04]">
                                <li>회원은 본인이 업로드하는 논문 및 데이터에 대한 적법한 저작권을 보유하고 있음을 보증해야 합니다.</li>
                                <li>타인의 저작권을 침해하는 콘텐츠를 업로드하여 발생하는 모든 법적 책임은 회원 본인에게 있습니다.</li>
                                <li>회사는 저작권 침해 신고가 접수될 경우, 해당 콘텐츠를 즉시 차단하거나 삭제할 수 있습니다.</li>
                            </ul>
                        </section>

                        <section>
                            <h3 className="font-display text-base font-bold text-white mb-2 flex items-center gap-2">
                                <span className="w-1 h-5 bg-highlight rounded-full"></span>
                                제3조 (데이터의 영구 저장)
                            </h3>
                            <p className="pl-3 border-l-2 border-white/[0.04]">본 서비스는 블록체인(IPFS/Polygon) 기술을 기반으로 하며, 업로드된 데이터는 위변조가 불가능한 형태로 영구 저장될 수 있습니다. 회원은 이에 동의하며, 기술적 특성상 삭제가 불가능할 수 있음을 인지합니다.</p>
                        </section>

                        <section>
                            <h3 className="font-display text-base font-bold text-white mb-2">제4조 (개인정보 수집 및 이용)</h3>
                            <ul className="list-disc pl-5 space-y-2">
                                <li>수집 항목: 지갑 주소, 이메일, 업로드 논문 메타데이터.</li>
                                <li>이용 목적: 서비스 제공, 보상 지급, 저작권 분쟁 해결.</li>
                                <li>보유 기간: 회원 탈퇴 시까지 (단, 블록체인에 기록된 정보는 영구 보존).</li>
                            </ul>
                        </section>
                    </div>

                    {/* Footer */}
                    <div className="p-6 border-t border-white/[0.06] bg-white/[0.02] rounded-b-2xl flex justify-end">
                        <button
                            onClick={onClose}
                            className="glass-button px-6 py-2 font-semibold"
                        >
                            확인
                        </button>
                    </div>
                </motion.div>
            </div>
        </AnimatePresence>
    );
};

export default Terms;
