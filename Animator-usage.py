from animator import Animate

anim = Animate(fps=60, enter_escape=True)
anim.print("Welcome to...")
anim.accii("Kiselgram", font="slant")

output = anim.start()          # press Enter when ready

if output:
    output.activate()          # 👈 overrides print/input globally
    print("This is coloured!")  # uses rainbow colour + black background
    name = input("Your name: ")
    print(f"Hello, {name}!")
    output.deactivate()        # restore normal print/input
print("Back to normal terminal.")