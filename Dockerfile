# 1. Use an official Python image
FROM python:3.11-slim

# 2. Set the working directory
WORKDIR /app

# 3. Copy requirements and install
# We do this before copying the rest of the code to speed up future builds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of your bot's code
COPY . .

# 5. CHANGE: Koyeb uses 8080 as the standard port
EXPOSE 8080

# 6. Start the bot
CMD ["python", "main.py"]