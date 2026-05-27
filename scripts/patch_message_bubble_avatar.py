from pathlib import Path

p = Path(r"C:\Users\dream\CCAI-Demo-Canvas-Upgrades\phd-advisor-frontend\src\components\MessageBubble.js")
c = p.read_text(encoding="utf-8")

start = c.index("    const avatarElement = (size = 40)")
end = c.index("    return (", start)
new = """    const avatarElement = (size = 44) => {
      const iconSize = Math.round(size * 0.52);
      return (
        <div
          className="advisor-message-avatar-ring"
          style={{ width: size, height: size }}
        >
          {advisor.avatarUrl ? (
            <img
              src={advisor.avatarUrl}
              alt={advisor.name || 'Advisor'}
            />
          ) : Icon ? (
            <Icon
              className="advisor-message-avatar-icon"
              style={{
                color: colors.color || 'var(--text-secondary)',
                width: iconSize,
                height: iconSize,
              }}
            />
          ) : (
            <span
              className="advisor-message-avatar-initial"
              style={{ color: colors.color || 'var(--text-secondary)', fontSize: iconSize }}
            >
              {advisor.name ? advisor.name.charAt(0) : 'A'}
            </span>
          )}
        </motion.div>
      );
    };

"""
new = new.replace("</motion.div>", "</" + "div>")

c = c[:start] + new + c[end:]
c = c.replace("{inlineAvatar && avatarElement(32)}", "{inlineAvatar && avatarElement(44)}", 1)
p.write_text(c, encoding="utf-8")
print("ok")
