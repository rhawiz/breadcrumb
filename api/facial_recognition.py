import os

from PIL import Image
from breadcrumbcore.ai import facialrecognition as fr

from breadcrumb import settings


def get_model():
    try:
        model_path = settings.FACIAL_RECOGNITION_MODEL_PATH or "face_recognition_model.pkl"
        if os.path.isfile(model_path):
            model = fr.load_model(settings.FACIAL_RECOGNITION_MODEL_PATH)
        else:
            dataset = fr.read_from_folder("./media/users/")
            model = fr.get_model(dataset)
            fr.save_model(model_path, model)
        return model
    except Exception as e:
        print e
        return None


def update_face_rec_model(image_path, identifier):
    model = get_model()
    dataset = fr.read_from_file(image_path, identifier)
    model.add_data(dataset)
    return model

def predict(image_path):
    try:
        model = get_model()
        converted_img_path = "temp_%s" % image_path
        fr.detect_face(image_path, outfile=converted_img_path)
        img = Image.open(converted_img_path)
        img = img.convert("L")
        p = model.predict(img)
        os.remove(converted_img_path)
        return p
    except Exception, e:
        print e
        return None
