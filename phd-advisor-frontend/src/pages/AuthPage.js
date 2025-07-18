import React, { useState } from 'react';
import Login from '../components/Login';
import Signup from '../components/Signup';

const AuthPage = ({ onAuthSuccess }) => {
  const [isLogin, setIsLogin] = useState(true);

  const handleNavigateToLogin = () => setIsLogin(true);
  const handleNavigateToSignup = () => setIsLogin(false);

  return (
    <>
      {isLogin ? (
        <Login 
          onNavigateToSignup={handleNavigateToSignup}
          onNavigateToHome={onAuthSuccess}
        />
      ) : (
        <Signup 
          onNavigateToLogin={handleNavigateToLogin}
          onNavigateToHome={onAuthSuccess}
        />
      )}
    </>
  );
};

export default AuthPage;