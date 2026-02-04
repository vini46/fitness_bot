# 1. Use an official Python image
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy your requirements file and install libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of your bot's code
COPY . .

# 5. Hugging Face expects a service on port 7860
EXPOSE 7860

# 6. Start the bot (replace 'app.py' if your file has a different name)
CMD ["python", "app.py"]