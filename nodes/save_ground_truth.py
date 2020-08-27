#!/usr/bin/python

import rospy
import os
import json
from rospy_message_converter import message_converter
import tf
import tf2_ros


class teach_repeat_ground_truth_save:
	def __init__(self):
		self.setup_parameters()
		self.setup_publishers()
		self.setup_subscribers()

	def setup_parameters(self):
		# data saving
		self.save_dir = os.path.expanduser(rospy.get_param('~folder', '~/data'))
		if self.save_dir[-1] != '/':
			self.save_dir += '/'
		if not os.path.isdir(self.save_dir):
			os.makedirs(self.save_dir)
		if not os.path.isdir(self.save_dir+'pose/'):
			os.makedirs(self.save_dir+'pose/')
		self.goal_number = 0
		
	def setup_publishers(self):	
		pass

	def setup_subscribers(self):
		self.tfBuffer = tf2_ros.Buffer()
		self.tfListener = tf2_ros.TransformListener(self.tfBuffer)

	def save_tf_data(self, pose, goal_odom, goal_world, theta_offset, path_offset):
		try:
			trans = self.tfBuffer.lookup_transform('map', 'base_link', rospy.Time())
			trans_as_text = json.dumps(message_converter.convert_ros_message_to_dictionary(trans))
			with open(self.save_dir + ('pose/%06d_map_to_base_link.txt' % self.goal_number), 'w') as pose_file:
				pose_file.write(trans_as_text)
		except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
			print('Could not lookup transform from /map to /base_link')
			pass


if __name__ == "__main__":
	rospy.init_node("teach_repeat_ground_truth_save")
	saver = teach_repeat_ground_truth_save()
	r = rospy.Rate(5)
	while not rospy.is_shutdown():
		saver.save_tf_data()
		r.sleep()