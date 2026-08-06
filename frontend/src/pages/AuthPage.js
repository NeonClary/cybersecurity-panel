import React, { useState } from 'react';
import Login from '../components/Login';
import Signup from '../components/Signup';
import GuestIntakeModal from '../components/GuestIntakeModal';

const AuthPage = ({ onAuthSuccess }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [showGuestIntake, setShowGuestIntake] = useState(false);

  const handleNavigateToLogin = () => setIsLogin(true);
  const handleNavigateToSignup = () => setIsLogin(false);

  return (
    <>
      {isLogin ? (
        <Login
          onNavigateToSignup={handleNavigateToSignup}
          onNavigateToHome={onAuthSuccess}
          onExploreAsGuest={() => setShowGuestIntake(true)}
        />
      ) : (
        <Signup
          onNavigateToLogin={handleNavigateToLogin}
          onNavigateToHome={onAuthSuccess}
          onExploreAsGuest={() => setShowGuestIntake(true)}
        />
      )}
      {showGuestIntake && (
        <GuestIntakeModal
          onClose={() => setShowGuestIntake(false)}
          onSuccess={(user, token) => {
            setShowGuestIntake(false);
            onAuthSuccess(user, token);
          }}
        />
      )}
    </>
  );
};

export default AuthPage;
