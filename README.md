# 📚 TOEIC Daily Bot

An automated Telegram bot designed to support daily TOEIC learning through scheduled vocabulary delivery, grammar quizzes, automated grading, and user-defined learning content.

The bot runs entirely on GitHub Actions, allowing it to operate automatically without requiring a personal computer or dedicated server.

## 🚀 Key Features

### Daily Vocabulary

- Sends **10 new vocabulary words per day**.
- Delivers 2 words at each scheduled time:
  - 08:00
  - 10:00
  - 12:00
  - 14:00
  - 16:00
- Users can review vocabulary learned during the day through the `/check` command.

### Grammar Practice

- Sends **10 TOEIC Part 5-style grammar questions** every day.
- The quiz is delivered at a randomly selected time between **08:00 and 23:00**.
- Users submit answers in a single message, for example:

```text
A C B D A B C D A B
