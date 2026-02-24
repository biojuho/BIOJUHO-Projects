/* eslint-disable react-refresh/only-export-components */
/**
 * Authentication Context
 * Manages user auth state with Firebase
 */
import { createContext, useContext, useState, useEffect } from 'react';
import {
    onAuthStateChanged,
    signInWithPopup,
    signInWithEmailAndPassword,
    createUserWithEmailAndPassword,
    signOut,
} from 'firebase/auth';
import { auth, googleProvider } from '../firebase';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [walletAddress, setWalletAddress] = useState(null);

    // Firebase error messages in Korean
    const getErrorMessage = (code) => {
        const messages = {
            'auth/email-already-in-use': '이미 사용 중인 이메일입니다.',
            'auth/invalid-email': '유효하지 않은 이메일 형식입니다.',
            'auth/weak-password': '비밀번호는 6자 이상이어야 합니다.',
            'auth/user-not-found': '등록되지 않은 이메일입니다.',
            'auth/wrong-password': '비밀번호가 올바르지 않습니다.',
            'auth/too-many-requests': '잠시 후 다시 시도해주세요.',
            'auth/popup-closed-by-user': '로그인이 취소되었습니다.',
            'auth/invalid-credential': '이메일 또는 비밀번호가 올바르지 않습니다.',
        };
        return messages[code] || '인증 오류가 발생했습니다.';
    };

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
            setUser(currentUser);
            setLoading(false);

            // Generate mock wallet if logged in but not connected real wallet
            if (currentUser && !walletAddress) {
                // Option: Keep it null to force user to connect, OR use Mock
                // For now, let's allow Mock as fallback for Demo
            }
        });
        return () => unsubscribe();
    }, [walletAddress]);

    // Connect Wallet (MetaMask/Rabby)
    const connectWallet = async () => {
        if (typeof window.ethereum !== 'undefined') {
            try {
                const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
                setWalletAddress(accounts[0]);
                return { success: true, address: accounts[0] };
            } catch (error) {
                return { success: false, error: error.message };
            }
        } else {
            return { success: false, error: "지갑이 설치되어 있지 않습니다." };
        }
    };

    // ... (Existing Google/Email functions)

    // Google Sign In
    const loginWithGoogle = async () => {
        try {
            const result = await signInWithPopup(auth, googleProvider);
            return { success: true, user: result.user };
        } catch (error) {
            return { success: false, error: getErrorMessage(error.code) };
        }
    };

    // Email Sign Up
    const signUpWithEmail = async (email, password) => {
        try {
            const result = await createUserWithEmailAndPassword(auth, email, password);
            return { success: true, user: result.user };
        } catch (error) {
            return { success: false, error: getErrorMessage(error.code) };
        }
    };

    // Email Sign In
    const loginWithEmail = async (email, password) => {
        try {
            const result = await signInWithEmailAndPassword(auth, email, password);
            return { success: true, user: result.user };
        } catch (error) {
            return { success: false, error: getErrorMessage(error.code) };
        }
    };

    // Sign Out
    const logout = async () => {
        try {
            await signOut(auth);
            setWalletAddress(null); // Clear wallet on logout
            return { success: true };
        } catch (error) {
            return { success: false, error: getErrorMessage(error.code) };
        }
    };

    const value = {
        user,
        loading,
        walletAddress,
        connectWallet,
        loginWithGoogle,
        signUpWithEmail,
        loginWithEmail,
        logout,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
