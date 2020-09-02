import os
import json
import math
import numpy as np
from rospy_message_converter import message_converter
from geometry_msgs.msg import Pose
import tf_conversions
import matplotlib.pyplot as plt
from tqdm import tqdm

def read_file(filename):
	with open(filename, 'r') as f:
		data = f.read()
	return data

def get_ground_truth_poses(dir):
	pose_files = np.array([f for f in os.listdir(dir) if f.endswith('_map_to_base_link.txt')])
	nums = [int(s.split('_')[0]) for s in pose_files]
	idx = np.argsort(nums)
	pose_files = [dir+f for f in pose_files[idx]]
	transforms = [message_converter.convert_dictionary_to_ros_message('geometry_msgs/TransformStamped',json.loads(read_file(p))).transform for p in pose_files]
	return [tf_conversions.fromMsg(Pose(tf.translation,tf.rotation)) for tf in transforms]

def get_pose_x_y_theta(poses):
	x = np.array([pose.p.x() for pose in poses])
	y = np.array([pose.p.y() for pose in poses])
	theta = np.array([pose.M.GetRPY()[2] for pose in poses])
	return np.vstack((x, y, theta))

def sample_repeats_to_teach(teach, repeats):
	'''Make the repeats the same length as teach, using the closest possible poses'''
	repeats_sampled = [np.zeros_like(teach) for r in repeats]
	window_half_size = 0.2 # search for match in corresponding 2*window_half_size of repeat run
	angle_threshold = math.radians(10) # make sure the matching poses are facing the same direction

	for i in range(teach.shape[1]):
		for j, r in enumerate(repeats):
			range_min = max(0, int(round((float(i) / teach.shape[1] - window_half_size) * r.shape[1])))
			range_max = min(r.shape[1], int(round((float(i) / teach.shape[1] + window_half_size) * r.shape[1])))
			r_window = r[:,range_min:range_max]
			dist = (r_window[0,:] - teach[0,i])**2 + (r_window[1,:] - teach[1,i])**2
			dist[abs(wrapToPi(r_window[2,:] - teach[2,i])) > angle_threshold] = np.nan
			if not np.all(np.isnan(dist)):
				best = np.nanargmin(dist)
				repeats_sampled[j][:,i] = r_window[:,best]
				repeats[j][:,best + range_min] = np.nan
			else:
				repeats_sampled[j][:,i] = np.full((3),np.nan)
	
	return repeats_sampled

def rotation_matrix(rad):
	return np.array(((math.cos(rad),-math.sin(rad)),(math.sin(rad),math.cos(rad))))

def get_repeat_errors(teach, repeats):
	'''With matching length teach and repeat runs, get the position error parallel and perpendicular to the teach path'''
	path_errors = [np.zeros((teach.shape[1])) for r in repeats]
	lateral_errors = [np.zeros((teach.shape[1])) for r in repeats]

	for i in range(teach.shape[1]):
		teach_pos = teach[:2,i]
		teach_angle = teach[2,i]
		for j, r in enumerate(repeats):
			repeat_pos = r[:2,i]
			pos_error = teach_pos - repeat_pos
			rotated_error = rotation_matrix(-teach_angle).dot(pos_error)
			path_errors[j][i] = rotated_error[0]
			lateral_errors[j][i] = rotated_error[1]
	return path_errors, lateral_errors

def wrapToPi(x):
	'''wrap angle to between +pi and -pi'''
	return ((x + math.pi) % (2*math.pi)) - math.pi

def quiver_plot(poses, colour):
	plt.quiver(poses[0], poses[1], np.cos(poses[2]), np.sin(poses[2]), color=colour, scale=50)

def line_plot(poses, colour):
	plt.plot(poses[0], poses[1], color=colour)

teach_run = os.path.expanduser('~/teach-repeat-data/teach/')
repeat_runs = ['~/teach-repeat-data/ours-filtered/','~/teach-repeat-data/bearnav-filtered/','~/teach-repeat-data/bearnav-unfiltered/']
repeat_runs = [os.path.expanduser(path) for path in repeat_runs]

teach_poses = get_pose_x_y_theta(get_ground_truth_poses(teach_run))
repeat_poses = [get_pose_x_y_theta(get_ground_truth_poses(repeat_dir)) for repeat_dir in repeat_runs]

colours = ['#44dd44', '#4444dd', '#dd4444', '#dddd44']

SHOW_DATA_FOR_CROPPING = False
if SHOW_DATA_FOR_CROPPING:
	fig, (ax1, ax2, ax3) = plt.subplots(3, 1, sharex=True)
	for pose_data_list,colour in zip(repeat_poses,colours[1:]):
		ax1.plot(pose_data_list[0], color=colour)
		ax2.plot(pose_data_list[1], color=colour)
		ax3.plot(pose_data_list[2], color=colour)
	ax1.set_title('Repeat runs')
	ax1.set_ylabel('x (m)')
	ax2.set_ylabel('y (m)')
	ax3.set_ylabel('theta (rad)')
	plt.legend([str(num) for num in list(range(len(repeat_poses)))])
	plt.show()
# crop to remove time spent standing still from repeat runs
repeat_poses[1] = repeat_poses[1][:,:1300]
repeat_poses[2] = repeat_poses[2][:,300:1800]

# match the size of repeat runs to the teach run (bearnav is sampled more often)
repeat_poses = sample_repeats_to_teach(teach_poses, repeat_poses)
repeat_errors_path, repeat_errors_lateral = get_repeat_errors(teach_poses, repeat_poses)
RMS_lateral = [math.sqrt(np.nanmean(errors_lateral**2)) for errors_lateral in repeat_errors_lateral]

# Show overview of the runs
plt.figure()
quiver_plot(teach_poses, colours[0])
for pose_data_list,colour in zip(repeat_poses,colours[1:]):
	quiver_plot(pose_data_list, colour)
plt.title('overview of runs')
plt.legend(['teach','ours (filtered odom)','bearnav (filtered odom)','bearnav (unfiltered odom)'])

# Show the lateral path error
# along path error doesn't make sense because the repeat run is sampled more frequently (for bearnav)
# so the along path error will always be tiny.
plt.figure()
for err_lateral,colour in zip(repeat_errors_lateral,colours[1:]):
	plt.plot(err_lateral, color=colour)
plt.title('Repeat run error')
plt.ylabel('lateral path error (m)')
plt.legend([
	'ours (filtered odom) RMS=%fm' % RMS_lateral[0],
	'bearnav (filtered odom) RMS=%fm' % RMS_lateral[1],
	'bearnav (unfiltered odom) RMS=%fm' % RMS_lateral[2]])
plt.show()