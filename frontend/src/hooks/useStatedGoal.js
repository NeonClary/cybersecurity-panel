import { useEffect, useState } from 'react';
import { resolveStatedGoal } from '../utils/statedGoal';

export default function useStatedGoal(authToken, user) {
  const [statedGoal, setStatedGoal] = useState(() => resolveStatedGoal({ user }));

  useEffect(() => {
    if (!authToken) {
      setStatedGoal(resolveStatedGoal({ user }));
      return undefined;
    }
    let cancelled = false;
    const apiUrl = process.env.REACT_APP_API_URL || '';
    (async () => {
      try {
        const [profileResp, factsResp] = await Promise.all([
          fetch(`${apiUrl}/api/users/me/profile`, {
            headers: { Authorization: `Bearer ${authToken}` },
          }),
          fetch(`${apiUrl}/api/users/me/facts`, {
            headers: { Authorization: `Bearer ${authToken}` },
          }),
        ]);
        const profile = profileResp.ok ? await profileResp.json() : null;
        const factsData = factsResp.ok ? await factsResp.json() : null;
        const facts = Array.isArray(factsData?.facts) ? factsData.facts : [];
        if (!cancelled) {
          setStatedGoal(resolveStatedGoal({ profile, facts, user }));
        }
      } catch {
        if (!cancelled) setStatedGoal(resolveStatedGoal({ user }));
      }
    })();
    return () => { cancelled = true; };
  }, [authToken, user]);

  return statedGoal;
}
