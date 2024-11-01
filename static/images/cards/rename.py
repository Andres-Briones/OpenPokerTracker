import os
import glob

# specify the file path and current file name
images = glob.glob("*.png")
print(images)

transform_dic = {
    'H':'h',
    'C':'c',
    'S':'s',
    'D':'d'
    }

for image in images:
    new_image_path = image[0] + transform_dic[image[1]] + '.png'
    os.rename(image, new_image_path)
