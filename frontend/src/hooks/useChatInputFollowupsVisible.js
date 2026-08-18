import { useCallback, useEffect, useState } from 'react';
import {
  readChatInputFollowupsVisible,
  writeChatInputFollowupsVisible,
  CHAT_INPUT_FOLLOWUPS_EVENT,
} from '../utils/chatInputFollowupsPref';

/** On/off for follow-up suggestion chips below the chat input. */
export default function useChatInputFollowupsVisible() {
  const [visible, setVisible] = useState(readChatInputFollowupsVisible);

  useEffect(() => {
    const sync = () => setVisible(readChatInputFollowupsVisible());
    window.addEventListener(CHAT_INPUT_FOLLOWUPS_EVENT, sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(CHAT_INPUT_FOLLOWUPS_EVENT, sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  const setFollowupsVisible = useCallback((next) => {
    setVisible(writeChatInputFollowupsVisible(next));
  }, []);

  const toggleFollowupsVisible = useCallback(() => {
    setVisible((prev) => writeChatInputFollowupsVisible(!prev));
  }, []);

  return {
    followupsVisible: visible,
    setFollowupsVisible,
    toggleFollowupsVisible,
  };
}
