import cv2
import PIL.Image
import io
from tracking import IOUModelTracking
from tqdm import tqdm
import os
import numpy as np
from model import Detector


def convert_img_to_rgb(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def convert_img_to_bytes(img):
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    im_out = PIL.Image.fromarray(img)
    f = io.BytesIO()
    im_out.save(f, format='png')
    return f.getvalue()


def save_video(frames, fps=16, file_name='/home/marcus/data/sber/CenterNet/src/heads.avi'):
    size = frames[0].shape[1], frames[0].shape[0]

    out = cv2.VideoWriter(
        file_name,
        fourcc=cv2.VideoWriter_fourcc(*'mp4v'),
        fps=fps,
        frameSize=size
    )

    for i in range(len(frames)):
        out.write(frames[i])

    out.release()


# VIDEO_FILE_NAME = '/home/marcus/data/sber/TUD-Stadtmitte.mp4'
# VIDEO_FILE_NAME = '/home/marcus/data/sber/MOT17-09-SDP.mp4'
# VIDEO_FILE_NAME = '/home/marcus/data/sber/MOT17-08-SDP.mp4'
# VIDEO_FILE_NAME = '/home/marcus/data/sber/MOT16-03.mp4'
VIDEO_FILE_NAME = '/home/marcus/data/sber/people_walking_russia.mp4'
# VIDEO_FILE_NAME = '/home/marcus/data/sber/P1033656.mp4'
# VIDEO_FILE_NAME = '/home/marcus/data/sber/P1033756.mp4'
# VIDEO_FILE_NAME = '/home/marcus/data/sber/forecaster/P1044014.mp4'
# VIDEO_FILE_NAME = '/home/marcus/data/sber/forecaster/P1033669.mp4'
# VIDEO_FILE_NAME = '/home/marcus/data/sber/forecaster/P1033788.mp4'


video = cv2.VideoCapture(VIDEO_FILE_NAME)

frames = list()
success, image = video.read()
frames.append(image)

while success:
    success, image = video.read()
    if success:
        frames.append(image)

det = Detector(score_threshold=0.75, nms_threshold=0.2)

tracking = IOUModelTracking(
    kalman=True,
    state_noise=1000.0, r_scale=5.0, q_var=100.0,
    iou_threshold=0.1, max_age=6, min_hits=2
)

output_detections = list()
tracked_frames = list()

blob_size = int(frames[0].shape[1] * 0.005)
line_width = int(frames[0].shape[1] * 0.005)

cycle_len = 32

draw_tracks = False
saved_tracks, saved_colors = None, None

for i in tqdm(range(len(frames))):
    next_frame = np.array(frames[i])
    next_frame_to_visual = np.array(next_frame)

    if draw_tracks and i % cycle_len != 0:
        trajectories, colors = saved_tracks, saved_colors
        for time_index in range(1, cycle_len):
            next_frame_to_visual = np.array(next_frame_to_visual)

            for traj, color in zip(trajectories, colors):
                x_start, y_start = traj[time_index - 1]
                x_end, y_end = traj[time_index]

                cv2.line(
                    next_frame_to_visual,
                    (x_start, y_start), (x_end, y_end),
                    color.tolist(), line_width
                )

    if i != 0 and i % cycle_len == 0:
        draw_tracks = True
        trajectories, colors = tracking.predict_trajectories(cycle_len, min_age=6)
        saved_tracks, saved_colors = trajectories, colors

        for time_index in range(1, cycle_len):
            next_frame_to_visual = np.array(next_frame_to_visual)

            for traj, color in zip(trajectories, colors):
                x_start, y_start = traj[time_index - 1]
                x_end, y_end = traj[time_index]

                cv2.line(
                    next_frame_to_visual,
                    (x_start, y_start), (x_end, y_end),
                    color.tolist(), line_width
                )

            tracked_frames.append(next_frame_to_visual)

        saved_frame_to_visual = np.array(next_frame_to_visual)

    pred = det.predict(convert_img_to_rgb(next_frame) / 255)


    def get_box_center(box):
        return ((box[1][0] + box[0][0]) // 2, (box[1][1] + box[0][1]) // 2)


    pred_boxes = [
        {
            'center': get_box_center(box),
            'box': box,
            'nose': (np.array(pred['left_shoulder'][index]) + np.array(pred['right_shoulder'][index])) / 2
        }
        for index, box in enumerate(pred['boxes'])
    ]

    tracked_detections = tracking.track(pred_boxes)

    for detection in tracked_detections:
        center = detection['nose']
        color = detection['color']
        box_center = detection['center']
        width, height = detection['box_size']

        x_min, x_max = int(box_center[0]) - width // 2, int(box_center[0]) + width // 2
        y_min, y_max = int(box_center[1]) - height // 2, int(box_center[1]) + height // 2

        cv2.circle(next_frame_to_visual, (int(center[0]), int(center[1])), blob_size, color.tolist(), -1)
    #         cv2.rectangle(next_frame_to_visual, (x_min, y_min), (x_max, y_max), color.tolist(), line_width)

    tracked_frames.append(next_frame_to_visual)

save_video(tracked_frames, fps=8, file_name='tracked_heads.mp4')

os.system('ffmpeg -i tracked_heads.mp4 -vcodec libx264 tracked_heads_2.mp4')
os.system('mv -f tracked_heads_2.mp4 tracked_heads.mp4')

