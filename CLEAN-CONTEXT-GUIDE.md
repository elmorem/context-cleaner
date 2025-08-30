# Clean Context Command Guide

> **Optimize your Claude Code context window for maximum LLM effectiveness**

## 🎯 What is `/clean-context`?

The `/clean-context` command is a powerful tool that analyzes and optimizes your current context window by:
- **Removing redundant information** - Eliminates duplicates and obsolete content
- **Prioritizing current work** - Places active tasks and relevant files at the top
- **Preventing context rot** - Removes stale or irrelevant information
- **Focusing LLM attention** - Ensures the most important context gets priority

---

## 🚀 Quick Start

### Basic Usage
```bash
/clean-context
```
This runs the full context optimization workflow with interactive preview and user approval.

### Quick Commands
```bash
/clean-context --dashboard    # View context health metrics only
/clean-context --quick        # Fast cleanup with safe defaults
/clean-context --preview      # Show proposed changes without applying
/clean-context --aggressive   # Maximum optimization with minimal confirmation
/clean-context --focus        # Reorder priorities without removing content
```

---

## 📊 Understanding Context Health

### Context Health Dashboard
When you run `/clean-context --dashboard`, you'll see metrics like:

```
🎯 FOCUS METRICS
├─ Focus Score: 73% (context relevant to current work)
├─ Priority Alignment: 45% (important items in top 25% of context)
├─ Current Work Ratio: 28% (active tasks vs total context)
└─ Attention Clarity: 62% (clear next steps vs noise)

🧹 REDUNDANCY ANALYSIS  
├─ Duplicate Content: 23% (repeated information detected)
├─ Stale Context: 18% (outdated information)
├─ Redundant Files: 4 files read multiple times
└─ Obsolete Todos: 7 completed/irrelevant tasks

⏱️ RECENCY INDICATORS
├─ Fresh Context: 35% (modified within last hour)
├─ Recent Context: 52% (modified within last session)
├─ Aging Context: 31% (older than current session)
└─ Stale Context: 17% (from previous unrelated work)

📈 SIZE OPTIMIZATION
├─ Total Context Size: 15,420 tokens (estimated)
├─ Optimization Potential: 32% reduction possible
├─ Critical Context: 68% must preserve
└─ Cleanup Impact: 4,934 tokens could be saved
```

### What These Metrics Mean

#### 🎯 Focus Metrics
- **Focus Score**: Percentage of context directly related to your current work
  - 🟢 80%+ = Excellent focus
  - 🟡 60-79% = Good, minor cleanup needed
  - 🔴 <60% = Poor focus, cleanup recommended

- **Priority Alignment**: Whether important items appear early in context
  - 🟢 70%+ = Well organized
  - 🟡 50-69% = Needs reordering
  - 🔴 <50% = Poorly organized

#### 🧹 Redundancy Analysis
- **Duplicate Content**: How much information is repeated
  - 🟢 <10% = Clean context
  - 🟡 10-25% = Moderate redundancy
  - 🔴 >25% = High redundancy, cleanup needed

#### ⏱️ Recency Indicators
- **Fresh/Recent Context**: How much relates to current work session
- **Stale Context**: Information from unrelated previous work

---

## 🔧 Optimization Modes

### Conservative Mode (Default)
**Best for**: First-time users, important work sessions, when unsure
- Only removes obvious duplicates and completed items
- Preserves all potentially relevant context
- Requests confirmation for all changes
- Minimal risk of losing important information

**Use when**: Working on critical tasks, debugging complex issues, or when context might contain important historical information

### Balanced Mode
**Best for**: Regular context maintenance, typical development sessions
- Applies standard cleanup rules automatically
- Moderate context consolidation
- Confirms only significant changes
- Good balance of optimization vs. safety

**Use when**: Regular development work, routine context cleanup, switching between related tasks

### Aggressive Mode
**Best for**: Heavy context bloat, starting fresh, experienced users
- Maximum redundancy elimination
- Extensive context consolidation
- Auto-applies most optimizations with minimal confirmation
- Highest optimization potential

**Use when**: Context is very cluttered, starting new major work, or you want maximum cleanup

---

## 📋 The Optimization Process

### Step 1: Health Dashboard
The command starts by showing you exactly what's in your context:
- Context composition breakdown (files, todos, conversations, etc.)
- Redundancy detection results
- Optimization opportunities identified
- Quick wins vs. complex changes

### Step 2: Automated Analysis
The system automatically identifies:
- **Immediate removal candidates**: Completed todos, resolved errors, obvious duplicates
- **Consolidation opportunities**: Multiple file reads, similar reminders, related todos
- **Priority reordering needs**: Current work buried in context, important items at bottom

### Step 3: Interactive Preview
Before making any changes, you see:
```
BEFORE CLEANUP (Current Context):
┌─ Context Size: 15,420 tokens
├─ Redundancy Level: 23% duplicate content
├─ Focus Score: 73% relevant to current work
└─ Identified Issues: 12 problems detected

AFTER CLEANUP (Proposed Changes):
┌─ Context Size: 10,486 tokens (-32% reduction)
├─ Redundancy Level: 8% (-15% improvement)
├─ Focus Score: 89% (+16% improvement)  
└─ Optimization Impact: 12 issues resolved

PROPOSED CHANGES:
✅ Remove: 7 completed todos, 4 duplicate file reads, 3 resolved errors
🔄 Consolidate: 2 related todo groups, 5 similar system reminders
🔝 Prioritize: Current work items, active files, ongoing debugging
📝 Summarize: 2 verbose conversation sections
```

### Step 4: Selective Approval
You have granular control:
- **✅ Approve All**: Apply all recommended optimizations
- **🎯 Selective Apply**: Choose specific optimizations to apply
- **❌ Reject Changes**: Cancel specific optimizations you want to keep
- **🔧 Custom Edit**: Manually adjust optimization parameters

### Step 5: Results & Analytics
After optimization, you receive:
- Context size reduction achieved
- Focus improvement metrics
- Optimization session summary
- Recommendations for future maintenance

---

## 🎯 When to Use `/clean-context`

### ✅ Good Times to Clean Context

**When starting new work:**
- Beginning a new feature or bug fix
- Switching between different project areas
- Starting a development session after a break

**When context feels cluttered:**
- Hard to find current work items
- Lots of completed todos still visible  
- Multiple reads of same files
- Context from previous debugging sessions

**Before important tasks:**
- Complex implementations requiring focus
- Code reviews or architectural decisions
- Performance optimization work
- Security-related changes

**After completing work:**
- Finished debugging a complex issue
- Completed a major feature
- Resolved multiple errors or problems

### ❌ Times to Avoid Cleaning

**During active debugging:**
- In the middle of investigating an issue
- When you need historical error context
- While tracking down intermittent problems

**When context is already organized:**
- Recent cleanup was already performed
- Context is already well-structured
- Working on multiple related tasks simultaneously

**Before complex analysis:**
- When you need detailed historical context
- During code archaeology or investigation
- When preserving conversation history is important

---

## 💡 Pro Tips

### Getting the Most from Context Cleaning

**1. Regular Maintenance**
- Run `/clean-context --dashboard` frequently to monitor health
- Use `/clean-context --quick` for routine maintenance
- Perform full cleanup when Focus Score drops below 70%

**2. Work Session Patterns**
- **Session Start**: `/clean-context --focus` to prioritize current work
- **During Work**: Monitor context health, avoid excessive file re-reads
- **Session End**: `/clean-context --quick` to clean up for next time

**3. Task Switching Strategy**
- Before switching tasks: `/clean-context --preview` to see what can be cleaned
- After major task completion: `/clean-context` full cleanup
- Emergency refocus: `/clean-context --focus` for quick prioritization

**4. Optimization Strategies**
- Start conservative, increase aggressiveness as you get comfortable
- Always preview major changes before applying
- Pay attention to analytics to learn your patterns

### Command Combinations

**Starting a new feature:**
```bash
/clean-context --aggressive  # Clean slate
/plan-eval-build            # Plan new work with clean context
```

**Debugging session cleanup:**
```bash
# After resolving issues
/clean-context --quick      # Remove resolved error context
/summarize                  # Capture key learnings
```

**Weekly context hygiene:**
```bash
/clean-context --stats      # Review optimization trends
/clean-context --dashboard  # Check current health
/clean-context              # Full optimization if needed
```

---

## 📈 Understanding Analytics

### Context Usage Analytics
After running cleanups, you'll build a history:

```
CLEANUP SESSION SUMMARY:
┌─ Optimization Date: 2024-01-15 14:30:22
├─ Context Reduction: 4,934 tokens (-32%)
├─ Focus Improvement: +16% relevance gain
├─ Items Removed: 7 duplicates, 11 obsolete, 4 stale
├─ Items Consolidated: 3 merged sections
├─ Priority Changes: 8 items reordered
└─ User Rating: 9/10 effectiveness score

HISTORICAL TRENDS (Last 30 days):
┌─ Avg Cleanup Frequency: Every 6.2 hours
├─ Avg Context Reduction: 28% per cleanup
├─ Most Common Issues: Duplicate files, completed todos, stale errors
├─ Best Optimization Wins: Priority reordering, redundancy removal
└─ Context Health Trend: Improving (+15% over month)
```

### Using Analytics to Improve
- **High cleanup frequency**: Consider more disciplined context habits
- **Low effectiveness ratings**: Try different optimization modes
- **Recurring issues**: Identify patterns to prevent future bloat
- **Health trends**: Track improvements in context management

---

## 🛠️ Advanced Usage

### Custom Analytics Commands
```bash
/clean-context --stats              # Show historical trends
/clean-context --health-check       # Quick assessment with recommendations
/clean-context --export-analytics   # Export data for external analysis
```

### Integration with Other Commands
```bash
# Workflow integration examples
/clean-context && /plan-eval-build  # Clean context before major planning
/read-summary && /clean-context     # Clean after loading historical context  
/clean-context --dashboard && /summarize  # Check health before session summary
```

### Automation and Monitoring
- Use `--dashboard` frequently to monitor context health
- Set up regular cleanup schedules based on your work patterns
- Watch for Context Health Trend indicators in analytics

---

## 🆘 Troubleshooting

### Common Issues

**"Context cleanup removed something important"**
- Use `--preview` mode to review changes before applying
- Start with `--conservative` mode until comfortable
- Context snapshots and undo functionality preserve safety

**"Optimization didn't improve focus much"**
- Try `--aggressive` mode for more thorough cleanup
- Check if your current work is properly defined in todos
- Consider if context is actually well-organized already

**"Cleanup is too slow or overwhelming"**
- Use `--quick` for fast, safe optimizations
- Focus on `--dashboard` first to understand issues
- Try `--focus` for priority reordering without major changes

### Getting Help
- Run `/clean-context --dashboard` to understand current context state
- Start with `--preview` to understand what changes are proposed
- Use `--conservative` mode for safety while learning the tool

---

## 🎖️ Best Practices Summary

### Daily Habits
1. **Monitor**: Check `--dashboard` regularly
2. **Quick Clean**: Use `--quick` between tasks  
3. **Focus**: Use `--focus` when work items get buried
4. **Preview**: Always preview major optimizations

### Weekly Maintenance
1. **Full Analysis**: Run complete `/clean-context` workflow
2. **Review Analytics**: Check `--stats` for improvement opportunities
3. **Health Check**: Use `--health-check` for trend analysis

### Project-Level Strategy
1. **Start Clean**: Begin major work with optimized context
2. **Maintain Focus**: Prioritize current work consistently
3. **End Clean**: Clean up after completing major tasks
4. **Learn Patterns**: Use analytics to improve context management skills

---

*Remember: The goal of `/clean-context` is to improve your LLM interactions by maintaining focused, relevant, and well-organized context. Start conservative, learn the patterns, and gradually increase optimization aggressiveness as you become comfortable with the tool.*

**Happy context cleaning! 🧹✨**