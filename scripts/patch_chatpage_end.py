from pathlib import Path

p = Path(r"C:\Users\dream\CCAI-Demo-Canvas-Upgrades\phd-advisor-frontend\src\pages\ChatPage.js")
c = p.read_text(encoding="utf-8")

close_div = "</" + "div>"

needle = f"""              placeholder={{
                replyingTo 
                  ? `Reply to ${{replyingTo.advisorName}}...`
                  : chatPlaceholder
              }}
            />
          {close_div}
        {close_div}
      {close_div}
    {close_div}
  );
}};

export default ChatPage;
"""

replacement = f"""              placeholder={{
                replyingTo 
                  ? `Reply to ${{replyingTo.advisorName}}...`
                  : chatPlaceholder
              }}
              showProfileButtons={{!userProfile || userProfile.completion_pct < 100}}
              onOpenOnboarding={{() => setShowOnboarding(true)}}
              onOpenProfileForm={{() => setShowProfileForm(true)}}
            />
          {close_div}
        {close_div}
      {close_div}

      {{showOnboarding && (
        <OnboardingChat
          authToken={{authToken}}
          userName={{user?.firstName}}
          onClose={{() => {{ setShowOnboarding(false); loadProfile(); }}}}
        />
      )}}

      {{showProfileForm && (
        <ProfileWalkthrough
          authToken={{authToken}}
          existingProfile={{userProfile}}
          onClose={{() => {{ setShowProfileForm(false); loadProfile(); }}}}
        />
      )}}

      {{showClearData && (
        <ClearDataModal
          authToken={{authToken}}
          onClose={{() => setShowClearData(false)}}
          onDataCleared={{({{ profile: clearedProfile, chats: clearedChats }}) => {{
            if (clearedProfile) {{
              setUserProfile(null);
              loadProfile();
            }}
            if (clearedChats) {{
              setMessages([]);
              setCurrentSessionId(null);
              setCurrentSessionTitle('');
              handleNewChat();
            }}
          }}}}
        />
      )}}

      {{showAccount && (
        <AccountModal
          user={{user}}
          authToken={{authToken}}
          onClose={{() => setShowAccount(false)}}
          onAccountUpdated={{(updated) => {{
            if (user) {{
              user.firstName = updated.firstName;
              user.lastName = updated.lastName;
              user.email = updated.email;
            }}
          }}}}
          onAccountDeleted={{() => {{
            setShowAccount(false);
            onSignOut();
          }}}}
        />
      )}}
    {close_div}
  );
}};

export default ChatPage;
"""

if needle not in c:
    raise SystemExit("needle not found in ChatPage.js")

p.write_text(c.replace(needle, replacement, 1), encoding="utf-8")
print("ok")
