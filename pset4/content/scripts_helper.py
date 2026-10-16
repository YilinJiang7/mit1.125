"""Video scene generation reuses the content writer's validated evidence reader."""
from articles_helper import write
from lib.records import stage_main

if __name__=='__main__':
    stage_main('write-video-scripts',lambda run,receipt:write(run,receipt,'script'),['python3','OpenAI API'])
