from pathlib import Path

p = Path(r"C:\Users\dream\CCAI-Demo-Canvas-Upgrades\phd-advisor-frontend\src\components\Sidebar.js")
c = p.read_text(encoding="utf-8")

avatar_old = (
    '                  <div className="user-avatar">\n'
    '                    <User size={20} />\n'
    '                  </div>'
)
avatar_new = (
    '                  <motion.div\n'
    '                    className="user-avatar"\n'
    '                    onClick={() => onAvatarChange && setShowAvatarPicker(true)}\n'
    '                    style={{\n'
    "                      cursor: onAvatarChange ? 'pointer' : undefined,\n"
    '                      backgroundColor: currentAvatar?.bg || undefined,\n'
    '                      color: currentAvatar?.color || undefined,\n'
    '                    }}\n'
    "                    title={onAvatarChange ? 'Change avatar' : undefined}\n"
    '                  >\n'
    '                    <AvatarIcon size={20} />\n'
    '                  </div>'
)
avatar_new = avatar_new.replace("<motion.div", "<div").replace("motion.div\n", "div\n")

menu_old = (
    '                    {showUserMenu && (\n'
    '                      <div className="user-menu">\n'
    '                        <button className="user-menu-item">\n'
    '                          <Settings size={16} />\n'
    '                          <span>Settings</span>\n'
    '                        </button>\n'
    '                        <button className="user-menu-item sign-out" onClick={onSignOut}>\n'
    '                          <LogOut size={16} />\n'
    '                          <span>Sign Out</span>\n'
    '                        </button>\n'
    '                      </div>\n'
    '                    )}'
)
menu_new = (
    '                    {showUserMenu && (\n'
    '                      <div className="user-menu">\n'
    '                        <button className="user-menu-item" onClick={() => { setShowUserMenu(false); setShowAvatarPicker(true); }}>\n'
    '                          <User size={16} />\n'
    '                          <span>Change Avatar</span>\n'
    '                        </button>\n'
    '                        <button className="user-menu-item" onClick={() => { setShowUserMenu(false); if (onOpenProfile) onOpenProfile(); }}>\n'
    '                          <UserCircle size={16} />\n'
    '                          <span>Profile</span>\n'
    '                        </button>\n'
    '                        <button className="user-menu-item" onClick={() => { setShowUserMenu(false); if (onOpenAccount) onOpenAccount(); }}>\n'
    '                          <KeyRound size={16} />\n'
    '                          <span>Account</span>\n'
    '                        </button>\n'
    '                        <button className="user-menu-item" onClick={() => { setShowUserMenu(false); if (onOpenClearData) onOpenClearData(); }}>\n'
    '                          <DatabaseZap size={16} />\n'
    '                          <span>Clear User Data</span>\n'
    '                        </button>\n'
    '                        <button className="user-menu-item sign-out" onClick={onSignOut}>\n'
    '                          <LogOut size={16} />\n'
    '                          <span>Sign Out</span>\n'
    '                        </button>\n'
    '                      </div>\n'
    '                    )}'
)

if avatar_old not in c:
    raise SystemExit("avatar block not found")
c = c.replace(avatar_old, avatar_new, 1)
if menu_old not in c:
    raise SystemExit("menu block not found")
c = c.replace(menu_old, menu_new, 1)

picker = """
      {showAvatarPicker && (
        <UserAvatarPicker
          options={avatarOptions}
          currentId={userAvatarId}
          onSelect={(id) => { onAvatarChange?.(id); setShowAvatarPicker(false); }}
          onClose={() => setShowAvatarPicker(false)}
        />
      )}
"""

if "UserAvatarPicker" not in c.split("export default")[0].split("return (")[-1]:
    c = c.replace(
        "      {isMobileOpen && (",
        picker + "\n      {isMobileOpen && (",
        1,
    )

p.write_text(c, encoding="utf-8")
print("Sidebar patched")
