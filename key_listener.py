
def on_press(key):
    try:
        print('Alphanummeric key pressed: {0} '.format(key.char))
    except AttributeError:
        print('special key pressed: {0}'.format(key))

def on_release(key):
    print('Key released: {0}'. format(key))
    if key == keyboard.Key.esc:
    # Stop listener
        return False



# with keyboard.Listener(on_press=on_press, onrelease=on_release) as listener:
#    listener.join()