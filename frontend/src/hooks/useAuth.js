import { useContext } from 'react';
import { AuthContext } from '../context/AuthContext.jsx';

/**
 * Custom Hook for shared authentication state
 * Usage:
 *   const { session, user, loading, signIn, signUp, signOut } = useAuth();
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
