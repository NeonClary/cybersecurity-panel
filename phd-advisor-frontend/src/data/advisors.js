import { BookOpen, Target, Brain } from 'lucide-react';

export const advisors = {
  methodologist: {
    name: 'Methodologist',
    role: 'Methodical Advisor',
    // Light theme colors
    color: '#3B82F6',
    bgColor: '#EFF6FF',
    // Dark theme colors
    darkColor: '#60A5FA',
    darkBgColor: '#1E3A8A',
    // Icon and description
    icon: BookOpen,
    description: 'Structured & Planning-focused'
  },
  theorist: {
    name: 'Theorist',
    role: 'Theoretical Advisor',
    // Light theme colors
    color: '#8B5CF6',
    bgColor: '#F3E8FF',
    // Dark theme colors
    darkColor: '#A78BFA',
    darkBgColor: '#581C87',
    // Icon and description
    icon: Brain,
    description: 'Abstract & Conceptual'
  },
  pragmatist: {
    name: 'Pragmatist',
    role: 'Practical Advisor',
    // Light theme colors
    color: '#10B981',
    bgColor: '#ECFDF5',
    // Dark theme colors
    darkColor: '#34D399',
    darkBgColor: '#065F46',
    // Icon and description
    icon: Target,
    description: 'Real-world & Outcome-focused'
  }
};

// Helper function to get theme-appropriate colors
export const getAdvisorColors = (advisorId, isDark = false) => {
  const advisor = advisors[advisorId];
  if (!advisor) return { color: '#6B7280', bgColor: '#F3F4F6' };
  
  return {
    color: isDark ? advisor.darkColor : advisor.color,
    bgColor: isDark ? advisor.darkBgColor : advisor.bgColor,
    // For text that needs to be readable on colored backgrounds
    textColor: isDark ? '#F9FAFB' : 
                advisor.color === '#10B981' ? '#047857' : // Darker green for pragmatist
                advisor.color === '#3B82F6' ? '#1D4ED8' : // Darker blue for methodologist  
                advisor.color === '#8B5CF6' ? '#7C3AED' : // Darker purple for theorist
                '#374151' // fallback
  };
};