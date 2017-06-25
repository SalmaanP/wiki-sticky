import json
import os
import time

import praw
import prawcore

SUBRDT = ''         # Subreddit name
WIKIPG = ''         # Name of wiki page with URL list
TIMING = 5          # Minutes between sticky updates

BOT_UN = ''         # Bot username
BOT_PW = ''         # Bot password
CLI_ID = ''         # Client ID
CLI_SC = ''         # Client secret


def main():
    reddit = initialize_reddit()
    i = 0
    err_index = None
    comments = load_processed_comments()
    time_thresh = 0
    while True:
        links = read_wiki(reddit)
        time_thresh, comments = check_the_comments(reddit, time_thresh, comments, links)

        if i >= len(links):
            i = 0
        try:
            reddit.submission(url=links[i]).mod.sticky()
        except (AssertionError, praw.exceptions.ClientException, prawcore.exceptions.Forbidden):
            print('Problem with URL %s (%d/%d). Stickying next link.' % (links[i], i + 1, len(links)))
            if err_index is None:
                err_index = i
            elif err_index == i:
                raise KeyboardInterrupt('There are no valid URLs in the wiki. Exiting to prevent an error loop.')
        else:
            print('Stickied URL %s (%d/%d)' % (links[i], i + 1, len(links)))
            err_index = None
            time.sleep(TIMING * 60)
        finally:
            i += 1


def initialize_reddit():
    reddit = praw.Reddit(
        client_id=CLI_ID,
        client_secret=CLI_SC,
        user_agent='praw:wiki_sticky:v1.1 (by /u/throwaway_the_fourth for /u/WaitinOnGST)',
        username=BOT_UN,
        password=BOT_PW
    )
    return reddit


def read_wiki(reddit):
    links = reddit.subreddit(SUBRDT).wiki[WIKIPG].content_md.split()
    if not links:
        raise KeyboardInterrupt('There is nothing in the wiki. Exiting to prevent an error loop.')
    return links


def write_wiki(reddit, links):
    reddit.subreddit(SUBRDT).wiki.create(WIKIPG, '\n\n'.join(links))


def load_processed_comments():
    try:
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'processed_comments.json')) as f:
            comments = json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        comments = []
    return comments


def write_processed_comments(comments):
    with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'processed_comments.json'), 'w') as f:
        json.dump(list(set(comments)), f)


def check_the_comments(reddit, time_thresh, comment_ids, links):
    # put the commands in a list, then handle them in the order they were posted
    commands = []
    new_ids = []
    for comment in reddit.subreddit(SUBRDT).comments():
        if comment.created_utc > time_thresh:
            if comment.body.strip().lower() in ['botsticky add', 'botsticky remove'] and \
                            comment.author in reddit.subreddit(SUBRDT).moderator() and \
                            comment.id not in comment_ids and comment.is_root:
                text = comment.body.strip().lower()
                new_ids.append(comment.id)
                commands.append((text, comment.submission.url))
        else:
            break
    comment_ids.extend(new_ids)
    if comment_ids is not None:
        write_processed_comments(comment_ids)

    url_change = False
    for command in reversed(commands):
        url = command[1]
        if command[0] == 'botsticky add' and url not in links:
            links.append(url)
            url_change = True
        elif command[0] == 'botsticky remove':
            while url in links:
                links.remove(url)
                url_change = True

    if url_change:
        write_wiki(reddit, links)

    return time.time(), comment_ids


if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            if e is KeyboardInterrupt:
                raise e
            else:
                print('Encountered an error. Restarting.')
                time.sleep(TIMING * 60)