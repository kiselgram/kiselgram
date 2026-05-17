import smtplib
smtp = smtplib.SMTP('mail.kiselgram.ru', 587)
smtp.starttls()
smtp.login('auth@mail.kiselgram.ru', 'KiselgramBackend2026')
print("Login successful")
smtp.quit()