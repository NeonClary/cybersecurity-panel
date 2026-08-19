import {
  VIEW_CHAT_ACTIVE,
  VIEW_CHAT_STARTER,
  chatActiveState,
  chatStarterState,
  homeState,
  isLeavingChatActive,
  mapPopState,
  sameHistoryState,
} from './chatHistoryNav';

describe('mapPopState', () => {
  test('null / missing state goes home so the original load entry is not trapped', () => {
    expect(mapPopState(null)).toEqual({
      currentView: 'home',
      chatNavView: null,
      sessionId: null,
    });
    expect(mapPopState({})).toEqual({
      currentView: 'home',
      chatNavView: null,
      sessionId: null,
    });
    expect(mapPopState(homeState())).toEqual({
      currentView: 'home',
      chatNavView: null,
      sessionId: null,
    });
  });

  test('leaving chat-active maps to starter; leaving starter maps to home', () => {
    expect(mapPopState(chatStarterState())).toEqual({
      currentView: 'chat',
      chatNavView: 'starter',
      sessionId: null,
    });
    expect(mapPopState(chatActiveState('abc'))).toEqual({
      currentView: 'chat',
      chatNavView: 'active',
      sessionId: 'abc',
    });
    expect(isLeavingChatActive(VIEW_CHAT_ACTIVE, mapPopState(chatStarterState()))).toBe(true);
    expect(isLeavingChatActive(VIEW_CHAT_STARTER, mapPopState(homeState()))).toBe(false);
  });

  test('canvas / journey / auth states restore those views', () => {
    expect(mapPopState({ view: 'canvas' }).currentView).toBe('canvas');
    expect(mapPopState({ view: 'journey' }).currentView).toBe('journey');
    expect(mapPopState({ view: 'auth' }).currentView).toBe('auth');
  });

  test('sameHistoryState compares view + session', () => {
    expect(sameHistoryState(chatActiveState('a'), chatActiveState('a'))).toBe(true);
    expect(sameHistoryState(chatActiveState('a'), chatActiveState('b'))).toBe(false);
    expect(sameHistoryState(chatStarterState(), homeState())).toBe(false);
  });
});
