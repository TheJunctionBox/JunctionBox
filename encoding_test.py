import curses
import time

utf8_string0 = 'Sigur Ros'
utf8_string1 = 'Sigur R\xc3\xb3s'
utf8_string2 = 'R\xc3\xb3s\xc3\xb3s\xc3\xb3s\xc3\xb3s'
start_time = 1800


def main():
    print "starting..."

    time.sleep(1)

    curses.wrapper(curses_stuff)


def format_time(seconds):
    seconds = int(seconds)
    secs = seconds % 60
    mins = (seconds - secs) / 60

    return str(mins).rjust(2, "0") + ":" + str(secs).rjust(2, "0")



def curses_stuff(stdscr):

    time_sec = start_time

    unicode_string0 = unicode(utf8_string0, 'utf-8')
    unicode_string1 = unicode(utf8_string1, 'utf-8')
    unicode_string2 = unicode(utf8_string2, 'utf-8')

    while True:
        print_string(stdscr, add_time(unicode_string0, time_sec), 0)
        print_string(stdscr, add_time(unicode_string1, time_sec), 1)
        print_string(stdscr, add_time(unicode_string2, time_sec), 2)
        time.sleep(1)
        time_sec += 1


def add_time(in_str, time_sec):
    time_string = unicode(format_time(time_sec), 'utf-8')
    return in_str[0:10].ljust(10, " ") + " " + time_string
    


def print_string(stdscr, in_str, row):
        utf8_output_string = in_str.encode('utf-8')
        stdscr.addstr(row * 6,     0, utf8_output_string)
        stdscr.addstr(row * 6 + 1, 0, utf8_output_string)
        stdscr.addstr(row * 6 + 2, 0, "1234567890123456")
        stdscr.addstr(row * 6 + 3, 0, str(len(utf8_output_string)))

        if row > 1:
            #stdscr.addstr(row * 6 + 5, 0, "redrawn")
            stdscr.redrawln(row * 6, 1)

        stdscr.refresh()




if __name__ == '__main__':
    main()
