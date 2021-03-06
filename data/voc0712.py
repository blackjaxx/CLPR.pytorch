"""VOC Dataset Classes

Original author: Francisco Massa
https://github.com/fmassa/vision/blob/voc_dataset/torchvision/datasets/voc.py

Updated by: Ellis Brown, Max deGroot
"""
from .config import HOME
import os.path as osp
import sys
import torch
import torch.utils.data as data
import cv2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import glob
from torch import randperm
if sys.version_info[0] == 2:
    import xml.etree.cElementTree as ET
else:
    import xml.etree.ElementTree as ET

VOC_CLASSES = (  # always index 0
    'aeroplane', 'bicycle', 'bird', 'boat',
    'bottle', 'bus', 'car', 'cat', 'chair',
    'cow', 'diningtable', 'dog', 'horse',
    'motorbike', 'person', 'pottedplant',
    'sheep', 'sofa', 'train', 'tvmonitor')

# note: if you used our download scripts, this should be right
VOC_ROOT = osp.join(HOME, "/media/chenjun/data/1_deeplearning/faster-rcnn.pytorch/data/VOCdevkit2007/")


class VOCAnnotationTransform(object):
    """Transforms a VOC annotation into a Tensor of bbox coords and label index
    Initilized with a dictionary lookup of classnames to indexes

    Arguments:
        class_to_ind (dict, optional): dictionary lookup of classnames -> indexes
            (default: alphabetic indexing of VOC's 20 classes)
        keep_difficult (bool, optional): keep difficult instances or not
            (default: False)
        height (int): height
        width (int): width
    """

    def __init__(self, class_to_ind=None, keep_difficult=False):
        self.class_to_ind = class_to_ind or dict(
            zip(VOC_CLASSES, range(len(VOC_CLASSES))))
        self.keep_difficult = keep_difficult

    def __call__(self, target, width, height):
        """
        Arguments:
            target (annotation) : the target annotation to be made usable
                will be an ET.Element
        Returns:
            a list containing lists of bounding boxes  [bbox coords, class name]
        """
        res = []
        for obj in target.iter('object'):
            difficult = int(obj.find('difficult').text) == 1
            if not self.keep_difficult and difficult:
                continue
            name = obj.find('name').text.lower().strip()
            bbox = obj.find('bndbox')

            pts = ['xmin', 'ymin', 'xmax', 'ymax']
            bndbox = []
            for i, pt in enumerate(pts):
                cur_pt = int(bbox.find(pt).text) - 1
                # scale height or width
                cur_pt = cur_pt / width if i % 2 == 0 else cur_pt / height
                bndbox.append(cur_pt)
            label_idx = self.class_to_ind[name]
            bndbox.append(label_idx)
            res += [bndbox]  # [xmin, ymin, xmax, ymax, label_ind]
            # img_id = target.find('filename').text[:-4]

        return res  # [[xmin, ymin, xmax, ymax, label_ind], ... ]


class VOCDetection(data.Dataset):
    """VOC Detection Dataset Object

    input is image, target is annotation

    Arguments:
        root (string): filepath to VOCdevkit folder.
        image_set (string): imageset to use (eg. 'train', 'val', 'test')
        transform (callable, optional): transformation to perform on the
            input image
        target_transform (callable, optional): transformation to perform on the
            target `annotation`
            (eg: take in caption string, return tensor of word indices)
        dataset_name (string, optional): which dataset to load
            (default: 'VOC2007')
    """

    def __init__(self, root,
                #  image_sets=[('2007', 'trainval'), ('2012', 'trainval')],
                 image_sets=[('2007', 'trainval')],
                 transform=None, target_transform=VOCAnnotationTransform(),
                 dataset_name='VOC0712'):
        self.root = root
        self.image_set = image_sets
        self.transform = transform
        self.target_transform = target_transform
        self.name = dataset_name
        self._annopath = osp.join('%s', 'Annotations', '%s.xml')
        self._imgpath = osp.join('%s', 'JPEGImages', '%s.jpg')
        self.ids = list()
        for (year, name) in image_sets:
            rootpath = osp.join(self.root, 'VOC' + year)
            for line in open(osp.join(rootpath, 'ImageSets', 'Main', name + '.txt')):
                self.ids.append((rootpath, line.strip()))

    def __getitem__(self, index):
        im, gt, h, w = self.pull_item(index)

        return im, gt

    def __len__(self):
        return len(self.ids)

    def pull_item(self, index):
        img_id = self.ids[index]

        target = ET.parse(self._annopath % img_id).getroot()
        img = cv2.imread(self._imgpath % img_id)
        height, width, channels = img.shape

        if self.target_transform is not None:
            target = self.target_transform(target, width, height)

        if self.transform is not None:
            target = np.array(target)
            img, boxes, labels = self.transform(img, target[:, :4], target[:, 4])
            # to rgb
            img = img[:, :, (2, 1, 0)]
            # img = img.transpose(2, 0, 1)
            target = np.hstack((boxes, np.expand_dims(labels, axis=1)))
        return torch.from_numpy(img).permute(2, 0, 1), target, height, width
        # return torch.from_numpy(img), target, height, width

    def pull_image(self, index):
        '''Returns the original image object at index in PIL form

        Note: not using self.__getitem__(), as any transformations passed in
        could mess up this functionality.

        Argument:
            index (int): index of img to show
        Return:
            PIL img
        '''
        img_id = self.ids[index]
        return cv2.imread(self._imgpath % img_id, cv2.IMREAD_COLOR)

    def pull_anno(self, index):
        '''Returns the original annotation of image at index

        Note: not using self.__getitem__(), as any transformations passed in
        could mess up this functionality.

        Argument:
            index (int): index of img to get annotation of
        Return:
            list:  [img_id, [(label, bbox coords),...]]
                eg: ('001718', [('dog', (96, 13, 438, 332))])
        '''
        img_id = self.ids[index]
        anno = ET.parse(self._annopath % img_id).getroot()
        gt = self.target_transform(anno, 1, 1)
        return img_id[1], gt

    def pull_tensor(self, index):
        '''Returns the original image at an index in tensor form

        Note: not using self.__getitem__(), as any transformations passed in
        could mess up this functionality.

        Argument:
            index (int): index of img to show
        Return:
            tensorized version of img, squeezed
        '''
        return torch.Tensor(self.pull_image(index)).unsqueeze_(0)


class ImgDataset(data.Dataset):
    def __init__(self, root=None, csv_root=None, transform=None, target_transform=None):
        self.root = root
        with open(csv_root) as f:
            self.data = f.readlines()
        self.transform = transform
        self.target_transform = target_transform
        self.name = 'ocr'

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        per_label = self.data[idx].rstrip().split('\t')
        imgpath = osp.join(self.root, per_label[0])
        img = cv2.imread(imgpath)
        height, width, channels = img.shape

        # 高度和宽度的归一化
        temp = [int(x) for x in per_label[2:6]]
        target1 = [[temp[0] / width, temp[1]/height, temp[2]/width, temp[3]/height, 0]]           # 归一化,target的类别是从0开始编码的

        if self.transform is not None:
            target = np.array(target1)
            img, boxes, labels = self.transform(img, target[:, :4], target[:, 4])
            # to rgb
            img = img[:, :, (2, 1, 0)]
            # img = img.transpose(2, 0, 1)
            target = np.hstack((boxes, np.expand_dims(labels, axis=1)))

        # 为ocr识别做的转换
        text = per_label[1].lstrip()
        if self.target_transform:
            data = self.target_transform(text)
        text = data[0]
        text_length = data[1]

        # 求rois
        rois = target1[0][:4]                   # rois是按图片的宽度和高度归一化之后的

        return torch.from_numpy(img).permute(2, 0, 1), target, height, width, text, text_length, rois


    def pull_image(self, idx):
        '''Returns the original image object at index in PIL form

        Note: not using self.__getitem__(), as any transformations passed in
        could mess up this functionality.

        Argument:
            index (int): index of img to show
        Return:
            PIL img
        '''
        per_label = self.data[idx].rstrip().split('\t')
        imgpath = osp.join(self.root, per_label[0])
        img = cv2.imread(imgpath, cv2.IMREAD_COLOR)
        return img


class LPDataset(data.Dataset):
    def __init__(self, root=None, csv_root=None, transform=None, target_transform=None):
        self.root = root
        temp = glob.glob(root)
        selected = randperm(len(temp), device=torch.device('cpu'))[:30000].tolist()             # 选30000张
        self.data = []
        self.data.extend(temp[x] for x in selected)
        self.transform = transform
        self.target_transform = target_transform
        self.name = 'ocr'
        self.provinces = ["皖", "沪", "津", "渝", "冀", "晋", "蒙", "辽", "吉", "黑", "苏", "浙", "京", "闽", "赣", "鲁", "豫", "鄂", "湘", "粤", "桂", "琼", "川", "贵", "云", "藏", "陕", "甘", "青", "宁", "新", "警", "学", "O"]
        self.alphabets = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W',
                        'X', 'Y', 'Z', 'O']
        self.ads = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X',
                    'Y', 'Z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'O']

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        per_name = self.data[idx]
        img = cv2.imread(per_name)
        height, width, channels = img.shape

        # 得到车牌区域
        per_name = per_name.split('/')[-1]
        data = per_name.split('-')[2].split('_')
        coor = []
        for t in data:
            coor.extend(t.split('&'))
        temp = [int(x) for x in coor]
        target1 = [[temp[0] / width, temp[1]/height, temp[2]/width, temp[3]/height, 0]]           # 归一化,target的类别是从0开始编码的

        # 数据增强
        if self.transform is not None:
            target = np.array(target1)
            img, boxes, labels = self.transform(img, target[:, :4], target[:, 4])
            # to rgb
            img = img[:, :, (2, 1, 0)]
            # img = img.transpose(2, 0, 1)
            target = np.hstack((boxes, np.expand_dims(labels, axis=1)))

        # ocr的字符转换
        label = per_name.split('-')[4]
        label = [int(x) for x in  label.split('_')]
        temp = [self.provinces[label[0]], self.alphabets[label[1]]] + [self.ads[x] for x in label[2:]]
        text = ''.join(temp)                    # 转换成字符串
        if self.target_transform:
            data = self.target_transform(text)
        text = data[0]
        text_length = data[1]

        # 求rois
        rois = target1[0][:4]                   # rois是按图片的宽度和高度归一化之后的

        return torch.from_numpy(img).permute(2, 0, 1), target, height, width, text, text_length, rois


    def pull_image(self, idx):
        '''Returns the original image object at index in PIL form

        Note: not using self.__getitem__(), as any transformations passed in
        could mess up this functionality.

        Argument:
            index (int): index of img to show
        Return:
            PIL img
        '''
        per_name = self.data[idx]
        img = cv2.imread(per_name, cv2.IMREAD_COLOR)
        return img