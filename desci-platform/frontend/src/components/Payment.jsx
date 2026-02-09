/**
 * Payment Component
 * 카카오페이 + 토스페이먼츠 결제 페이지
 */
import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { auth } from '../firebase';

const BIOLINKER_API = import.meta.env.VITE_BIOLINKER_URL || 'http://localhost:8001';

/** 인증 헤더 포함 axios 인스턴스 */
async function apiCall(method, path, data) {
    const token = await auth.currentUser?.getIdToken();
    return axios({
        method,
        url: `${BIOLINKER_API}${path}`,
        data,
        headers: {
            'Content-Type': 'application/json',
            ...(token && { Authorization: `Bearer ${token}` }),
        },
    });
}

export default function Payment() {
    const { user } = useAuth();
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [products, setProducts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [processing, setProcessing] = useState(false);
    const [result, setResult] = useState(null);

    // 결제 성공 콜백 처리
    const provider = searchParams.get('provider');
    const orderId = searchParams.get('order_id');
    const pgToken = searchParams.get('pg_token');

    useEffect(() => {
        fetchProducts();
    }, []);

    // 카카오페이 결제 승인 콜백
    useEffect(() => {
        if (provider === 'kakao' && orderId && pgToken) {
            approveKakao(orderId, pgToken);
        }
    }, [provider, orderId, pgToken]);

    async function fetchProducts() {
        try {
            const res = await axios.get(`${BIOLINKER_API}/payment/products`);
            setProducts(res.data);
        } catch (err) {
            console.error('상품 로딩 실패:', err);
        } finally {
            setLoading(false);
        }
    }

    // ============ 카카오페이 ============

    async function handleKakaoPay(productId) {
        setProcessing(true);
        try {
            const res = await apiCall('post', '/payment/kakao/ready', {
                product_id: productId,
            });
            const data = res.data;
            if (data.success) {
                // 카카오페이 결제 페이지로 리다이렉트
                const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                const redirectUrl = isMobile
                    ? data.redirect_mobile_url
                    : data.redirect_url;
                window.location.href = redirectUrl;
            }
        } catch (err) {
            alert('카카오페이 결제 준비 실패: ' + (err.response?.data?.detail || err.message));
        } finally {
            setProcessing(false);
        }
    }

    async function approveKakao(orderId, pgToken) {
        setProcessing(true);
        try {
            const res = await axios.post(
                `${BIOLINKER_API}/payment/kakao/approve?order_id=${orderId}&pg_token=${pgToken}`
            );
            setResult({ success: true, ...res.data });
        } catch (err) {
            setResult({ success: false, error: err.response?.data?.detail || err.message });
        } finally {
            setProcessing(false);
        }
    }

    // ============ 토스페이먼츠 ============

    async function handleTossPay(product) {
        setProcessing(true);
        try {
            // 클라이언트 키 가져오기
            const keyRes = await axios.get(`${BIOLINKER_API}/payment/toss/client-key`);
            const clientKey = keyRes.data.client_key;

            if (!clientKey) {
                alert('토스페이먼츠 설정이 필요합니다 (.env에 TOSS_CLIENT_KEY 설정)');
                setProcessing(false);
                return;
            }

            // 토스 결제 위젯 로드
            const { loadTossPayments } = await import('@tosspayments/tosspayments-sdk');
            const tossPayments = await loadTossPayments(clientKey);
            const orderId = `DSCI-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

            const payment = tossPayments.payment({ customerKey: user?.uid || 'guest' });

            await payment.requestPayment({
                method: 'CARD',
                amount: { currency: 'KRW', value: product.amount },
                orderId,
                orderName: product.name,
                successUrl: `${window.location.origin}/payment/success?provider=toss`,
                failUrl: `${window.location.origin}/payment/fail`,
            });
        } catch (err) {
            if (err.code === 'USER_CANCEL') {
                // 사용자 취소
            } else {
                alert('토스 결제 실패: ' + (err.message || '알 수 없는 오류'));
            }
        } finally {
            setProcessing(false);
        }
    }

    // ============ 결제 결과 화면 ============

    if (result) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 flex items-center justify-center p-8">
                <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-10 border border-white/20 max-w-md w-full text-center">
                    {result.success ? (
                        <>
                            <div className="text-6xl mb-4">&#10003;</div>
                            <h2 className="text-2xl font-bold text-white mb-2">결제 완료!</h2>
                            <p className="text-gray-300 mb-2">{result.item_name || '상품'}</p>
                            <p className="text-cyan-400 text-xl font-bold mb-6">
                                {(result.amount || 0).toLocaleString()}원
                            </p>
                            <p className="text-gray-400 text-sm mb-6">
                                주문번호: {result.order_id}
                            </p>
                        </>
                    ) : (
                        <>
                            <div className="text-6xl mb-4">&#10007;</div>
                            <h2 className="text-2xl font-bold text-red-400 mb-2">결제 실패</h2>
                            <p className="text-gray-300 mb-6">{result.error}</p>
                        </>
                    )}
                    <button
                        onClick={() => { setResult(null); navigate('/payment'); }}
                        className="px-6 py-3 bg-cyan-500 hover:bg-cyan-600 text-white rounded-xl font-bold transition-all"
                    >
                        돌아가기
                    </button>
                </div>
            </div>
        );
    }

    // ============ 상품 목록 + 결제 선택 ============

    return (
        <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 p-8">
            <div className="max-w-5xl mx-auto">
                <h2 className="text-3xl font-bold text-white mb-2">결제 / 충전</h2>
                <p className="text-gray-400 mb-8">카카오페이 또는 토스페이먼츠로 결제할 수 있습니다</p>

                {loading ? (
                    <div className="text-center py-20">
                        <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-cyan-400 mx-auto" />
                    </div>
                ) : (
                    <div className="grid md:grid-cols-2 gap-6">
                        {products.map((product) => (
                            <div
                                key={product.id}
                                className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20 hover:border-cyan-400/50 transition-all"
                            >
                                <h3 className="text-xl font-bold text-white mb-2">{product.name}</h3>
                                <p className="text-gray-400 text-sm mb-4">{product.description}</p>
                                <p className="text-3xl font-bold text-cyan-400 mb-6">
                                    {product.amount.toLocaleString()}
                                    <span className="text-base text-gray-400 ml-1">원</span>
                                </p>

                                <div className="flex gap-3">
                                    {/* 카카오페이 */}
                                    <button
                                        onClick={() => handleKakaoPay(product.id)}
                                        disabled={processing}
                                        className="flex-1 py-3 bg-[#FEE500] hover:bg-[#FDD835] text-[#191919] rounded-xl font-bold transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                                    >
                                        <span className="text-lg">K</span>
                                        카카오페이
                                    </button>

                                    {/* 토스페이먼츠 */}
                                    <button
                                        onClick={() => handleTossPay(product)}
                                        disabled={processing}
                                        className="flex-1 py-3 bg-[#0064FF] hover:bg-[#0050CC] text-white rounded-xl font-bold transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                                    >
                                        <span className="text-lg">T</span>
                                        토스페이
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {/* 안내 */}
                <div className="mt-8 bg-white/5 rounded-2xl p-6 border border-white/10">
                    <h3 className="text-white font-bold mb-3">결제 안내</h3>
                    <ul className="text-gray-400 text-sm space-y-2">
                        <li>- 카카오페이: QR 코드 또는 카카오톡 앱으로 간편 결제</li>
                        <li>- 토스페이먼츠: 카드, 계좌이체, 토스페이 등 다양한 결제 수단</li>
                        <li>- 결제 완료 후 즉시 서비스가 활성화됩니다</li>
                        <li>- 문의: support@desci-decentbio.com</li>
                    </ul>
                </div>
            </div>
        </div>
    );
}


/**
 * 토스 결제 성공 콜백 페이지
 * /payment/success?provider=toss&paymentKey=...&orderId=...&amount=...
 */
export function PaymentSuccess() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const provider = searchParams.get('provider');
        if (provider === 'toss') {
            confirmToss();
        }
    }, []);

    async function confirmToss() {
        const paymentKey = searchParams.get('paymentKey');
        const orderId = searchParams.get('orderId');
        const amount = parseInt(searchParams.get('amount'), 10);

        try {
            const res = await axios.post(`${BIOLINKER_API}/payment/toss/confirm`, {
                payment_key: paymentKey,
                order_id: orderId,
                amount,
            });
            setResult({ success: true, ...res.data });
        } catch (err) {
            setResult({ success: false, error: err.response?.data?.detail || err.message });
        } finally {
            setLoading(false);
        }
    }

    if (loading) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 flex items-center justify-center">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-cyan-400 mx-auto mb-4" />
                    <p className="text-white">결제 확인 중...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 flex items-center justify-center p-8">
            <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-10 border border-white/20 max-w-md w-full text-center">
                {result?.success ? (
                    <>
                        <div className="text-6xl mb-4 text-green-400">&#10003;</div>
                        <h2 className="text-2xl font-bold text-white mb-2">결제 완료!</h2>
                        <p className="text-cyan-400 text-xl font-bold mb-2">
                            {(result.amount || 0).toLocaleString()}원
                        </p>
                        <p className="text-gray-400 text-sm mb-6">
                            결제 수단: {result.method || '-'}
                        </p>
                    </>
                ) : (
                    <>
                        <div className="text-6xl mb-4 text-red-400">&#10007;</div>
                        <h2 className="text-2xl font-bold text-red-400 mb-2">결제 실패</h2>
                        <p className="text-gray-300 mb-6">{result?.error}</p>
                    </>
                )}
                <button
                    onClick={() => navigate('/payment')}
                    className="px-6 py-3 bg-cyan-500 hover:bg-cyan-600 text-white rounded-xl font-bold transition-all"
                >
                    돌아가기
                </button>
            </div>
        </div>
    );
}
