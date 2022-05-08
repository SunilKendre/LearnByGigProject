from telegram import constants, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, Dispatcher, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
from models import User, Gig, Step, GigUser, StepGigUser
from dbhelper import Session, engine
from datetime import datetime
import logging
import boto3
import os
from dotenv import load_dotenv
import requests
from botocore.exceptions import NoCredentialsError
from telegram.bot import BotCommand
from bot_commands import suggested_commands
from sqlalchemy.orm import load_only

load_dotenv()

log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(format=log_format, level=logging.INFO)
logger = logging.getLogger(__name__)

# TOKEN = os.environ.get('CTOGIGS_TELEGRAM_TOKEN')
#TOKEN = '2098863676:AAFJHIw5MkNnWePBzSQAMFTYrKWCCXsgplg'
TOKEN = '2031223066:AAHuzIOlzycEXq-whPTNSrW_Q28PtgOXRqc'

show_all_gigs_limit = 5
DESC, STEPS, INSTRUCTIONS = range(3)
WORKCOMMENT, WORKLINK, WORKPHOTO = range(3)
SELECTED_OPTION, SELECTED_DESCRIPTION, SELECTED_STEPS, STEP_EDITION, SELECTED_INSTRUCTIONS = range(5)
SELECTED_USER, STEP_REVIEW, REVIEW = range(3)
STEP_ENTERED, STEP_OPERATION, SELECTED_COMMENT, SELECTED_LINKS, SELECTED_PHOTOS = range(5)
# ADMIN_CHAT_IDS = [1031241092, 1748983631]
#ADMIN_CHAT_IDS = [1066103338]     # Mine 1066103338
ADMIN_CHAT_IDS = [1031241092]

submitgigstep_timeout_time = 120
addgig_timeout_time = 120
checkgigusersub_timeout_time = 120
END = ConversationHandler.END
nl = '\n'

FOLDERNAME_USERWORKS = 'userworks/'
if not os.path.isdir(FOLDERNAME_USERWORKS):
    os.mkdir(FOLDERNAME_USERWORKS)

BUCKET_NAME = 'work-photos-ctogigsbot'


def save_file_locally(filepath_to_download, filename_to_store):
    response = requests.get(filepath_to_download)
    final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
    try:
        logger.info(f"Inside /addlog. Saving image locally")
        with open(final_file_path, 'wb') as f:
            f.write(response.content)
        logger.info("Image Saved locally..")
        return True
    except:
        logger.info("Image could not be saved locally..")
        return False


def save_file_in_s3(filepath_to_download, bucket, filename_to_store):
    s3 = boto3.client('s3', region_name='us-east-1')
    try:
        logger.info(f"Inside /addlog. Saving image on S3")
        imageResponse = requests.get(filepath_to_download, stream=True).raw
        final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
        s3.upload_fileobj(imageResponse, bucket, final_file_path)
        logger.info("Image Saved on S3..")
        return True
    except FileNotFoundError:
        logger.error('File not found..')
        return False
    except NoCredentialsError:
        logger.info('Credentials not available')
        return False
    except:
        logger.info('Some other error saving the file to S3')
        return END


def get_current_user(session, update):
    chat_id = update.message.chat_id
    user = User.get_user_by_chatid(session=session, chat_id=chat_id)
    if user:
        return user
    else:
        update.message.reply_text('Use /start first then use this command again!')
        return None


def help(update, context):
    update.message.reply_text("This bot allows you to explore and register for <b><i>python/fullstack/ml-dl-nlp/blockchain</i></b> related gigs."
                              "\n\nUse '/' to see list of all supported/usable commands!", parse_mode='HTML')


def start(update, context):
    logging.info('Inside start')
    first_name = update.message.from_user.first_name
    last_name = None
    if update.message.from_user.last_name:
        last_name = update.message.from_user.last_name
    chat_id = update.message.chat_id
    tg_username = None
    if update.message.from_user.username:
        tg_username = update.message.from_user.username
    created_at = datetime.now()
    with Session() as session:
        user = User.get_user_by_chatid(session=session, chat_id=chat_id)
        if not user:
            user = User(chat_id=chat_id, first_name=first_name, last_name=last_name, tg_username=tg_username,
                        created_at=created_at)
            session.add(user)
            try:
                session.commit()
                update.message.reply_text(f"Welcome to LearnByGigs!, {user.first_name.title()}")
            except:
                session.rollback()
        else:
            update.message.reply_text(f"Welcome back, {user.first_name.title()}")


def allgigs(update, context):
    with Session() as session:
        user = get_current_user(session=session, update=update)
        if not user:
            return
        all_gigs = session.query(Gig).order_by(Gig.created_at.desc()).limit(show_all_gigs_limit).all()
        if not all_gigs:
            update.message.reply_text("No any gig exist yet!")
            return
        update.message.reply_text(f'Showing latest {show_all_gigs_limit} gigs:')
        for gig in all_gigs:

            final_steps = nl.join([f"{_id+1}. {step.step_text}" for _id, step in enumerate(gig.steps.all())])
            update.message.reply_text(f"<b>Gig Id:</b> {gig.id}\n\n"
                                      f"<b>Desc:</b> {gig.short_description}\n\n"
                                      f"<b>Steps:</b> \n{final_steps}\n\n"
                                      f"<b>Instructions:</b> {gig.instructions}", parse_mode='HTML')


def mygigs(update, context):
    with Session() as session:
        current_user = get_current_user(session=session, update=update)
        if not current_user:
            return

        if not current_user.gigs:
            update.message.reply_text("You haven't taken any gigs yet!")
            return
        update.message.reply_text('You have registered for the following gigs:')
        for gig in current_user.gigs:
            update.message.reply_text(f"<b>Gig Id:</b> {gig.id}\n\n"
                                      f"<b>Desc:</b> {gig.short_description}\n\n"
                                      f"<b>Steps:</b>\n{nl.join([f'{_id+1}. {step.step_text}' for _id, step in enumerate(gig.steps.all())])}\n\n"
                                      f"<b>Instructions:</b> {gig.instructions}", parse_mode='HTML')


def giginfo(update, context):
    with Session() as session:
        user = get_current_user(session=session, update=update)
        if not user:
            return
        if not context.args:
            update.message.reply_text('You need to pass gig id next to the command.\n'
                                      '<i>e.g. /giginfo 1 or /giginfo 2</i>', parse_mode='HTML')
            return
        recv_id = context.args[0]
        try:
            recv_id = int(recv_id)
        except:
            update.message.reply_text('Only number can be passed next to the command. Text not allowed.')
            return
        gig = Gig.get_gig(session=session, id=recv_id)
        if not gig:
            update.message.reply_text(f"Gig id #{recv_id} does not exist")
        else:

            final_steps = nl.join([f"{_id + 1}. {step.step_text}" for _id, step in enumerate(gig.steps.all())])
            update.message.reply_text(f"<b>Gig Id:</b> {gig.id}\n\n"
                                      f"<b>Desc:</b> {gig.short_description}\n\n"
                                      f"<b>Steps:</b> \n{final_steps}\n\n"
                                      f"<b>Instructions:</b> {gig.instructions}", parse_mode='HTML')


def takegig(update, context):
    with Session() as session:
        current_user = get_current_user(update=update, session=session)
        if not current_user:
            return
        if not context.args:
            update.message.reply_text('You need to pass gig id next to the command.\n'
                                     '<i>e.g. /takegig 1 or /takegig 2</i>', parse_mode='HTML')
            return
        recv_id = context.args[0]
        try:
            recv_id = int(recv_id)
        except:
            update.message.reply_text('Only number can be passed next to the command. Text not allowed.')
            return

        current_gig = Gig.get_gig(session=session, id=recv_id)
        if not current_gig:
            update.message.reply_text(f'Gig id #{recv_id} does not exist!')
            return
        giguser = GigUser.get_giguser_by_gigid_userid(session=session, gigid=recv_id, userid=current_user.id)
        if not giguser:
            current_user.gigusers.append(GigUser(gig_id=recv_id))
            session.add(current_user)
            try:
                session.commit()
                update.message.reply_text(f'You have signed up for gig #{recv_id}. Use /mygigs for check your gigs.')
            except:
                session.rollback()
                update.message.reply_text('Something went wrong. Please try again!')
        else:
            update.message.reply_text(f"You have already signed up for gig #{recv_id}. Use /mygigs for check your gigs")


def addgig(update, context):
    chat_id = update.message.chat_id
    if chat_id not in ADMIN_CHAT_IDS:
        update.message.reply_text('You do not have access to use this command')
        return END
    update.message.reply_text("Write description in short (Use /newgigcancel to cancel).")
    return DESC


def desc_of_new_gig(update, context: CallbackContext):
    description = update.message.text
    chat_data = context.chat_data
    chat_data['desc'] = description
    update.message.reply_text("Got the description. \nWrite steps one by one (Use /stepdone once done).")
    return STEPS


def steps_of_new_gig(update, context):
    steps = update.message.text
    chat_data = context.chat_data
    if not chat_data.get('steps'):
        chat_data['steps'] = list()
    chat_data['steps'].append(steps)
    return STEPS


def done_with_steps(update, context):
    update.message.reply_text("Steps noted. \n Write instructions if any (otherwise say 'no').")
    return INSTRUCTIONS


def instructions_of_new_gig(update, context):
    instructions = update.message.text
    update.message.reply_text("That's it!")
    chat_data = context.chat_data
    chat_data['instructions'] = instructions
    save_new_gig(update, context)
    return END


def save_new_gig(update, context):
    chat_id = update.message.chat_id
    chat_data = context.chat_data
    short_description = chat_data['desc']
    instructions = chat_data['instructions']
    steps = chat_data['steps']
    owner_chat_id = chat_id
    gig = Gig(short_description=short_description, instructions=instructions, owner_chat_id=owner_chat_id, created_at=datetime.now(), updated_at=datetime.now())
    with Session() as session:
        session.add(gig)
        try:
            session.commit()
        except:
            session.rollback()
            update.message.reply_text("Error while saving gig in database!")
            return END
        for localstepid, step in enumerate(steps):
            step_obj = Step(localstepid=localstepid + 1, gig_id=gig.id, step_text=step)
            session.add(step_obj)
        try:
            session.commit()
            final_steps = nl.join([f"{_id + 1}. {step.step_text}" for _id, step in enumerate(gig.steps.all())])
            update.message.reply_text(f"Gig successfully created! \n\nThe details of gig are given below:\n"
                                      f"<b>Gig Id:</b> {gig.id}\n"
                                      f"<b>Desc:</b> {gig.short_description}\n" 
                                      f"<b>Steps:</b> \n{final_steps}\n"
                                      f"<b>Instructions:</b> {gig.instructions}", parse_mode='HTML')
            chat_data.clear()
            logger.info('chat_data cleared')
            return END
        except:
            session.rollback()
            update.message.reply_text("Error while saving steps in database!")
            # return END


def newgigcancel(update, context):
    update.message.reply_text("Adding new gig Cancelled!")
    chat_data = context.chat_data
    chat_data.clear()
    return END


def submitgigstep(update, context):
    with Session() as session:
        user = get_current_user(session=session, update=update)
        if not user:
            return END
        if not context.args:
            update.message.reply_text("You need to pass gig id next to the command.")
            return END
        recv_id = context.args[0]
        try:
            recv_id = int(recv_id)
        except:
            update.message.reply_text('Only number is can be passed next to the command. Text not allowed.')
            return END
        gig = Gig.get_gig(session=session, id=recv_id)
        if not gig:
            update.message.reply_text(f"Gig id #{recv_id} does not exist! Please enter correct gig id.")
            return
        giguser = GigUser.get_giguser_by_gigid_userid(session=session, userid=user.id, gigid=gig.id)
        if not giguser:
            update.message.reply_text(f"You need to TAKE this gig first. Use '/takegig {gig.id}' to register for that gig!")
            return END
        steps_submitted = giguser.stepgigusers.all()
        global_step_to_submit = gig.steps.all()[0].id
        local_step_to_submit = gig.steps.filter(Step.id == global_step_to_submit).first().localstepid
        if not steps_submitted and local_step_to_submit == 1:
            update.message.reply_text(
                f'Accepting your work for <b>Step {local_step_to_submit} (global step id {global_step_to_submit})</b> of <b>Gig {recv_id}</b> '
                f'(Use /cancelsubmission to cancel submission of step.)\n\n'
                f'This is FIRST STEP for which you are submitting your work!\n\n'
                f'Write comment if any (Use /skipcomment to skip).', parse_mode='HTML')
        else:
            local_step_to_submit = len(steps_submitted)
            steps_submitted_list = [stepgiguser.step_id for stepgiguser in steps_submitted]
            last_step_submitted = max(steps_submitted_list)
            last_step_of_gig = gig.steps.all()[-1].id
            if last_step_submitted == last_step_of_gig:
                update.message.reply_text(f"You have submitted all the steps of {gig.id}! \nYour gig submission is complete!")
                return END
            elif last_step_submitted < last_step_of_gig:
                global_step_to_submit = max(steps_submitted_list) + 1
                update.message.reply_text(f"You have already submitted work for step #{local_step_to_submit} (global step id #{global_step_to_submit - 1})!\n\n"
                                          f"Now, submit your work for step #{local_step_to_submit + 1} (global step id {global_step_to_submit}) (Use /cancelsubmission to cancel).\n"
                                          f"Write comment if any (Use /skipcomment to skip).")

        chat_data = context.chat_data
        chat_data['gig_id'] = gig.id
        chat_data['giguser_id'] = giguser.id
        chat_data['local_step_id'] = local_step_to_submit
        chat_data['global_step_to_submit'] = global_step_to_submit
    return WORKCOMMENT


def submit_work_comment(update, context):
    chat_data = context.chat_data
    work_comment = update.message.text
    chat_data['work_comment'] = work_comment
    update.message.reply_text("Got your comment.\n"
                              "Share github/drive/youtube link that points to your work for step or video demonstration of the step (Use /donelinks once done).")
    return WORKLINK


def submit_work_link(update, context):
    link = update.message.text
    chat_data = context.chat_data
    if not chat_data.get('work_link_temp'):
        chat_data['work_link_temp'] = list()
    chat_data['work_link_temp'].append(link)
    return WORKLINK


def submit_work_photo(update, context):
    update.message.reply_text("Photo received. Processing")
    our_file = update.effective_message.photo[-1]
    if our_file:
        try:
            file_id = our_file.file_id
            # file_unique_id = our_file.file_unique_id
            actual_file = our_file.get_file()

            filepath_to_download = actual_file['file_path']

            ext = filepath_to_download.split('.')[-1]
            filename_to_store = f"{file_id}.{ext}"

            logger.info(f"Inside /submitgigstep. Got photo. Saving photo as- {filename_to_store}")
            update.message.reply_chat_action(action=constants.CHATACTION_UPLOAD_PHOTO)

            status = save_file_locally(filepath_to_download=filepath_to_download, filename_to_store=filename_to_store)
            # status = save_file_in_s3(filepath_to_download=filepath_to_download, bucket=BUCKET_NAME,
            #                          filename_to_store=filename_to_store)
            if status:
                update.message.reply_text('Image uploaded successfully..')
            else:
                update.message.reply_text("Image not uploaded. Plz try again!")
                return END
            chat_data = context.chat_data
            if not chat_data.get('work_photo_temp'):
                chat_data['work_photo_temp'] = list()
            final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
            chat_data['work_photo_temp'].append(final_file_path)
            logger.info(f"Inside /submitgigstep. Got photo. Final work photos - {chat_data['work_photo_temp']}")
        except:
            logger.error(f"Update {update} caused error WHILE SAVING PHOTO- {context.error}")
            logger.error(f"Exception while saving photo", exc_info=True)
    update.message.reply_text('Photo processed, successfully!')
    return WORKPHOTO


def skipcomment(update, context):
    update.message.reply_text('Skipping comment.')
    chat_data = context.chat_data
    chat_data['work_comment'] = None
    update.message.reply_text("Share github/drive/youtube link that points to your work for step or video demonstration of the step (Use /donelinks once done).")
    return WORKLINK


def no_text_allowed(update, context):
    update.message.reply_text("Only photos are accepted. Submit photo of your work for the respective step!")
    return WORKPHOTO


def donelinks(update, context):
    chat_data = context.chat_data
    if not chat_data.get('work_link_temp'):
        chat_data['work_links'] = None
    else:
        chat_data['work_links'] = ',,,'.join(chat_data['work_link_temp'])
    update.message.reply_text('Next, upload photos of code/output if any (Use /donephotos once done).')
    return WORKPHOTO


def donephotos(update, context):
    chat_data = context.chat_data
    if not chat_data.get('work_photo_temp'):
        chat_data['work_photos'] = None
        logger.info(f"Inside /submitgigstep. /donephotos. No work photos so storing chat_data['work_photos'] to None")
    else:
        chat_data['work_photos'] = ',,,'.join(chat_data['work_photo_temp'])  # deliberately using this instead of comma, bcz if user somehow enters , in his work links, then it'll be split unnecessarily. so we want some unique identifier.

    status = save_gig_submission(update, context)


def cancelsubmission(update, context):
    update.message.reply_text('Gig submission cancelled.')
    chat_data = context.chat_data
    chat_data.clear()
    return END


def save_gig_submission(update, context):
    chat_data = context.chat_data
    gig_id = chat_data['gig_id']
    giguser_id = chat_data['giguser_id']
    step_id = chat_data['global_step_to_submit']
    local_step_id = chat_data['local_step_id']
    work_comment = chat_data['work_comment']
    work_links = chat_data['work_links']
    work_photos = chat_data['work_photos']
    update.message.reply_text('Alright. Saving your record')

    stepgiguser = StepGigUser(step_id=step_id, giguser_id=giguser_id, work_comment=work_comment, work_photo=work_photos, work_link=work_links, submitted_at=datetime.now())
    with Session() as session:
        session.add(stepgiguser)
        try:
            session.commit()
            append_file_ids = []
            if stepgiguser.work_photo:
                photos = stepgiguser.work_photo.split(',,,')
                for photo in photos:
                    if photo.find('userworks/') != -1:
                        file_id = photo.split('userworks/')[-1].split('.')[0]
                        append_file_ids.append(file_id)

            update.message.reply_text(f"You have successfully submitted <b>step #{local_step_id}</b> of <i>gig #{gig_id}</i> (Use '/checkgigsub {gig_id}' for check submission of gig).\n\n"
                                      f"The details of <b>step #{local_step_id}</b> of <i>gig #{gig_id}</i> are given below:\n"
                                      f"{'<b>Work Comment:</b>' + stepgiguser.work_comment + nl if stepgiguser.work_comment else ''}"
                                      f"{'<b>Work Link:</b>' + stepgiguser.work_link.replace(',,,', nl) + nl if stepgiguser.work_link else ''}"
                                      f"{'' if not append_file_ids else '<b>Work Photo: </b>'}", parse_mode='HTML',
                                      disable_web_page_preview=True)
            for file in append_file_ids:
                update.message.reply_photo(file)
            chat_data.clear()
            logger.info('chat_data cleared')
        except:
            update.message.reply_text("Error while step submission of gig!")
            session.rollback()
        return END


def checkgigsub(update, context):
    with Session() as session:
        user: User = get_current_user(session=session, update=update)
        if not user:
            return
        if not context.args:
            update.message.reply_text('You need to pass gig id next to the command.\n'
                                      '<i>e.g. /checkgigsub 1 or /checkgigsub 2</i>', parse_mode='HTML')
            return
        recv_id = context.args[0]
        try:
            recv_id = int(recv_id)
        except:
            update.message.reply_text('Only number can be passed next to the command. Text not allowed.')
            return
        gig = Gig.get_gig(session=session, id=recv_id)
        if not gig:
            update.message.reply_text(f"Gig id #{recv_id} does not exist")
            return
        giguser = GigUser.get_giguser_by_gigid_userid(session=session, gigid=gig.id, userid=user.id)
        if not giguser:
            update.message.reply_text(f"First, you need to TAKE the gig #{recv_id}. Use '/takegig {recv_id}' to register for that gig!")
            return
        if not giguser.stepgigusers.all():
            update.message.reply_text(f"You haven't submitted any step for gig id #{recv_id}")
            return
        update.message.reply_text(f"The submission of <i>gig #{recv_id}</i> is given below:", parse_mode='HTML')
        for _id, item in enumerate(giguser.stepgigusers.all()):
            append_file_ids = []
            if item.work_photo:
                photos = item.work_photo.split(',,,')
                for photo in photos:
                    if photo.find('userworks/') != -1:
                        file_id = photo.split('userworks/')[-1].split('.')[0]
                        append_file_ids.append(file_id)

            update.message.reply_text(f"<b>Step Id:</b> {_id + 1}\n\n"
                                      f"<b>Submitted at:</b> {item.submitted_at.strftime('%d %b %Y, %I:%M %p') if item.submitted_at else ''}\n\n"
                                      f"<b>Review:</b> {item.review}{nl * 2}"
                                      f"<b>Reviewed at:</b> {item.reviewed_at.strftime('%d %b %Y, %I:%M %p') if item.reviewed_at else None}{nl*2}"
                                      f"{'<b>Work Comment:</b>' + item.work_comment + nl * 2 if item.work_comment else ''}"
                                      f"{'<b>Work Link:</b>' + item.work_link.replace(',,,', nl) + nl * 2 if item.work_link else ''}"
                                      f"{'' if not append_file_ids else '<b>Work Photo: </b>'}", parse_mode='HTML', disable_web_page_preview=True)
            for file in append_file_ids:
                update.message.reply_photo(file)


def deletegig(update, context):
    chat_data = context.chat_data
    chat_id = update.message.chat_id
    if chat_id not in ADMIN_CHAT_IDS:
        update.message.reply_text('You do not have access to do this command')
        return END
    with Session() as session:
        if not context.args:
            update.message.reply_text('You need to pass gig id next to the command.\n'
                                      '<i>e.g. /deletegig 1 or /deletegig 2</i>', parse_mode='HTML')
            return END
        recv_id = context.args[0]
        try:
            recv_id = int(recv_id)
            chat_data['recv_id'] = recv_id
        except:
            update.message.reply_text('Only number can be passed next to the command. Text not allowed.')
            return END
        gig = Gig.get_gig(session=session, id=recv_id)
        if not gig:
            update.message.reply_text(f"Gig id #{recv_id} does not exist")
            return END
            # obj = session.query(StepGigUser).values('work_link').filter(StepGigUser.work_link == link).first()
        session.query(Gig).filter(Gig.id == recv_id).delete()
        # session.delete(obj)


        try:
            session.commit()
            update.message.reply_text(f"Gig #{recv_id} deleted")
        except:
            session.rollback()
            print("Something went wrong!")
            update.message.reply_text("Something went wrong!")
            # sesion.delete(recv_id)
            # context.args[0]=None



def editgig(update, context):
    chat_data = context.chat_data
    chat_id = update.message.chat_id
    if chat_id not in ADMIN_CHAT_IDS:
        update.message.reply_text('You do not have access to do this command')
        return END
    with Session() as session:
        if not context.args:
            update.message.reply_text('You need to pass gig id next to the command.\n'
                                      '<i>e.g. /editgig 1 or /editgig 2</i>', parse_mode='HTML')
            return END
        recv_id = context.args[0]
        try:
            recv_id = int(recv_id)
            chat_data['recv_id'] = recv_id
        except:
            update.message.reply_text('Only number can be passed next to the command. Text not allowed.')
            return END
        gig = Gig.get_gig(session=session, id=recv_id)
        if not gig:
            update.message.reply_text(f"Gig id #{recv_id} does not exist")
            return END
        else:
            keyboard = [
                [
                    InlineKeyboardButton("Edit Description", callback_data='editdescription'),
                    InlineKeyboardButton("Edit Steps", callback_data='editsteps'),
                    InlineKeyboardButton("Edit Instructions", callback_data='editinstructions'),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            final_steps = nl.join([f"{_id + 1}. {step.step_text}" for _id, step in enumerate(gig.steps.all())])
            update.message.reply_text(f"Details of <i>gig #{recv_id}</i> are given below (Use /canceledit to cancel):\n\n"
                                      f"<b>Gig Id:</b> {gig.id}\n"
                                      f"<b>Desc:</b> {gig.short_description}\n"
                                      f"<b>Steps:</b> \n{final_steps}\n"
                                      f"<b>Instructions:</b> {gig.instructions}", parse_mode='HTML', reply_markup=reply_markup)
            return SELECTED_OPTION


def edit_option(update, context):
    with Session() as session:
        chat_data = context.chat_data
        gig = Gig.get_gig(session=session, id=chat_data['recv_id'])
        if not gig:
            return
        query = update.callback_query
        query.answer()
        if query.data == 'editdescription':
            query.edit_message_text(text=f"Enter new description.")
            return SELECTED_DESCRIPTION
        elif query.data == 'editsteps':
            chat_data = context.chat_data
            recv_id = chat_data['recv_id']

            query.edit_message_text(text=f"Enter <b>step_id</b> which you want to edit.{nl}{nl}"
                                         f"The steps of <i>gig #{recv_id}</i> are given below:\n"
                                         f"{nl.join([f'{_id + 1}. {step.step_text}' for _id, step in enumerate(gig.steps.all())])}", parse_mode='HTML')
            return SELECTED_STEPS
        elif query.data == 'editinstructions':
            query.edit_message_text(text=f"Enter new instructions.")
            return SELECTED_INSTRUCTIONS
        else:
            query.edit_message_text(text=f"Something is wrong. Try again later.")
            return END


def selected_description(update, context):
    with Session() as session:
        description = update.message.text
        chat_data = context.chat_data
        gig = Gig.get_gig(session=session, id=chat_data['recv_id'])
        description = gig.update_description(session=session, description=description)
        if description:
            update.message.reply_text(f"Updated new description - {description.short_description}")
        else:
            update.message.reply_text("Error While updating description!")
        return END


def selected_steps(update, context):
    with Session() as session:
        step_id = update.message.text
        try:
            step_id = int(step_id)
        except:
            update.message.reply_text("Step id must be integer. Please enter correct step_id.")
            return
        chat_data = context.chat_data
        chat_data['step_id'] = step_id
        gig = Gig.get_gig(session=session, id=chat_data['recv_id'])
        step = gig.steps.filter(Step.localstepid == step_id).first()
        chat_data['step'] = step
        if not step:
            update.message.reply_text(f"Step id #{step_id} does not exist. Please enter correct step_id.")
            return
        update.message.reply_text("Write step")
        return STEP_EDITION


def selected_instructions(update, context):
    with Session() as session:
        chat_data = context.chat_data
        instructions = update.message.text
        gig = Gig.get_gig(session=session, id=chat_data['recv_id'])
        instruction = gig.update_instructions(session=session, instructions=instructions)
        if instruction:
            update.message.reply_text(f"New instructions - {instruction.instructions}")
        else:
            update.message.reply_text("Error while updating instructions!")
        return END


def canceledit(update, context):
    update.message.reply_text("Editing cancelled!")
    chat_data = context.chat_data
    chat_data.clear()
    return END


def checksubwithgiguserid(update, context):
    chat_id = update.message.chat_id
    if chat_id not in ADMIN_CHAT_IDS:
        update.message.reply_text('You do not have access to do this command')
        return END
    with Session() as session:
        if not context.args:
            update.message.reply_text('You need to pass giguser id next to the command.\n'
                                      '<i>e.g. /checksubwithgiguserid 1 or /checksubwithgiguserid 2</i>', parse_mode='HTML')
            return END
        recv_id = context.args[0]
        try:
            recv_id = int(recv_id)
        except:
            update.message.reply_text('Only number can be passed next to the command.')
            return END
        giguser = GigUser.get_giguser_by_id(session=session, id=recv_id)
        if not giguser:
            update.message.reply_text(f"Giguser id #{recv_id} not present!")
            return END
        user = giguser.user
        user_first_name = user.first_name
        user_last_name = user.last_name
        update.message.reply_text(f"Submission of gig #{giguser.gig_id} for user {user_first_name} {user_last_name}is given below:\n\n")
        for _id, item in enumerate(giguser.stepgigusers.filter(StepGigUser.giguser_id == recv_id).all()):
            append_file_ids = []
            if item.work_photo:
                photos = item.work_photo.split(',,,')
                for photo in photos:
                    if photo.find('userworks/') != -1:
                        file_id = photo.split('userworks/')[-1].split('.')[0]
                        append_file_ids.append(file_id)

            update.message.reply_text(f"<b>Step Id:</b> {_id + 1}\n\n"
                                      f"<b>Submitted at:</b> {item.submitted_at.strftime('%d %b %Y, %I:%M %p') if item.submitted_at else ''}\n\n"
                                      f"{'<b>Work Comment:</b>' + item.work_comment + nl * 2 if item.work_comment else ''}"
                                      f"{'<b>Work Link:</b>' + item.work_link.replace(',,,', nl) + nl * 2 if item.work_link else ''}"
                                      f"{'' if not append_file_ids else '<b>Work Photo: </b>'}", parse_mode='HTML', disable_web_page_preview=True)
            for file in append_file_ids:
                update.message.reply_photo(file)


def checkgigusersub(update, context):
    with Session() as session:
        chat_id = update.message.chat_id
        if chat_id not in ADMIN_CHAT_IDS:
            update.message.reply_text('You do not have access to use this command')
            return END
        if not context.args:
            update.message.reply_text('You need to pass gig id next to the command.\n'
                                      '<i>e.g. /checkgigusersub 1 or /checkgigusersub 2</i>', parse_mode='HTML')
            return END
        recv_id = context.args[0]
        try:
            recv_id = int(recv_id)
            chat_data = context.chat_data
            chat_data['gig_id'] = recv_id
        except:
            update.message.reply_text('Only number can be passed next to the command. Text not allowed.')
            return END
        gig = Gig.get_gig(session=session, id=recv_id)
        if not gig:
            update.message.reply_text(f"Gig id #{recv_id} does not exist")
            return END
        if gig.users:
            update.message.reply_text(f"Enter <b>user_id</b> of user whose work you want to check (Use /cancelprocess to cancel).{nl}\nList of users who taken <i>gig #{recv_id}</i> is given below:"
                                      f"""{nl}{nl.join([f'{item.id}. {item.first_name.title()} {item.last_name.title() if item.last_name else ""}' for item in gig.users])}""", parse_mode='HTML')
            return SELECTED_USER
        else:
            update.message.reply_text(f"No any user taken the gig #{recv_id}")


def selected_user(update, context):
    with Session() as session:
        user_id = update.message.text
        try:
            user_id = int(user_id)
        except:
            update.message.reply_text("Only numbers can be passed next to the command. Please enter correct user_id.")
            return
        user = User.get_user_by_id(session=session, id=user_id)
        if not user:
            update.message.reply_text(f"User id #{user_id} does not exist! Please enter correct user_id.")
            return
        chat_data = context.chat_data
        chat_data['user_id'] = user_id
        gig_id = chat_data['gig_id']
        giguser = GigUser.get_giguser_by_gigid_userid(session=session, gigid=gig_id, userid=user_id)
        chat_data['giguser_id'] = giguser.id
        update.message.reply_text(f"The work of <b>{user.first_name.title()} {user.last_name.title() if user.last_name else ''}</b> for <i>gig #{gig_id}</i> is given below:", parse_mode='HTML')
        for _id, step in enumerate(giguser.stepgigusers.filter(StepGigUser.giguser_id == giguser.id).all()):
            append_file_ids = []
            if step.work_photo:
                photos = step.work_photo.split(',,,')
                for photo in photos:
                    if photo.find('userworks/') != -1:
                        file_id = photo.split('userworks/')[-1].split('.')[0]
                        append_file_ids.append(file_id)

            update.message.reply_text(f"<b>Step Id:</b> {_id +1 if step.step_id else ''}{nl}"
                                      f"{'<b>Work Comment:</b> ' + step.work_comment if step.work_comment else ''}{nl}"
                                      f"{'<b>Work Link:</b> ' + step.work_link if step.work_link else ''}{nl}"
                                      f"{'' if not step.work_photo else '<b>Work Photo:</b> '}", parse_mode='HTML', disable_web_page_preview=True)
            for file in append_file_ids:
                update.message.reply_photo(file)
        update.message.reply_text("Enter <b>step_id</b> for which you want to give review.", parse_mode='HTML')
        return STEP_REVIEW


def step_edition(update, context):
    with Session() as session:
        step_text = update.message.text
        chat_data = context.chat_data
        step = chat_data['step']
        update_step = step.update_step(session=session, step_text=step_text)
        if update_step:
            update.message.reply_text(f"Updated step - {step.step_text}")
        else:
            update.reply_text("Error while updating step!")
        return END


def review(update, context):
    with Session() as session:
        chat_data = context.chat_data
        giguser_id = chat_data['giguser_id']
        global_id = chat_data['global_id']
        review = update.message.text
        data = StepGigUser.get_stepgiguser_by_stepid_giguserid(session=session, stepid=global_id, giguserid=giguser_id)
        updated_review = data.update_review(session=session, review=review)
        if updated_review:
            update.message.reply_text(f"Updated review - {updated_review.review}")
        else:
            update.message.reply_text("Error while updating review!")
        return END


def review_step(update, context):
    with Session() as session:
        step_id = update.message.text
        chat_data = context.chat_data
        try:
            step_id = int(step_id)
            chat_data['step_id'] = step_id
        except:
            update.message.reply_text("Only number can be passed. Please enter correct step_id!")
            return
        chat_data = context.chat_data
        gig_id = chat_data['gig_id']
        gig = Gig.get_gig(session=session, id=gig_id)
        try:
            global_step_to_submit = gig.steps.all()[step_id - 1].id
        except:
            update.message.reply_text(f"Step #{step_id} for <i>gig #{gig_id}</i> does not exist! Please enter correct step_id.", parse_mode='HTML')
            return
        chat_data['global_id'] = global_step_to_submit
        update.message.reply_text(f"Write review for step #{step_id} of gig #{gig_id}.")
        return REVIEW


def cancelprocess(update, context):
    chat_data = context.chat_data
    chat_data.clear()
    update.message.reply_text("Process cancelled!")
    return END


def editgigsub(update, context):
    with Session() as session:
        chat_data = context.chat_data
        user = get_current_user(session=Session, update=update)
        chat_data['user'] = user
        if not user:
            return END
        if not context.args:
            update.message.reply_text('You need to pass gig id next to the command.\n'
                                      '<i>e.g. /editgigsub 1 or /editgigsub 2</i>', parse_mode='HTML')
            return END
        recv_id = context.args[0]
        try:
            recv_id = int(recv_id)
        except:
            update.message.reply_text('Only number can be passed next to the command. Text not allowed.')
            return END
        gig = Gig.get_gig(session=session, id=recv_id)
        chat_data['gig'] = gig
        chat_data['gig_id'] = recv_id
        if not gig:
            update.message.reply_text(f"Gig with id - {recv_id} does not exist")
            return END
        giguser = GigUser.get_giguser_by_gigid_userid(session=session, gigid=recv_id, userid=user.id)
        chat_data['giguser'] = giguser
        if not giguser:
            update.message.reply_text(f"You haven't taken gig #{recv_id}. Use '/takegig {recv_id}' to take gig #{recv_id}.")
            return END
        if not giguser.stepgigusers.all():
            update.message.reply_text(f"You haven't submitted any step for gig #{recv_id}")
            return END
        update.message.reply_text(f"The submission of <i>gig #{recv_id}</i> is given below:", parse_mode='HTML')
        for _id, item in enumerate(giguser.stepgigusers):
            append_file_ids = []
            if item.work_photo:
                photos = item.work_photo.split(',,,')
                for photo in photos:
                    if photo.find('userworks/') != -1:
                        file_id = photo.split('userworks/')[-1].split('.')[0]
                        append_file_ids.append(file_id)

            update.message.reply_text(f"<b>Step Id:</b> {_id + 1}\n\n"
                                      f"<b>Submitted at:</b> {item.submitted_at.strftime('%d %b %Y, %I:%M %p') if item.submitted_at else ''}\n\n"
                                      f"{'<b>Work Comment:</b>' + item.work_comment + nl * 2 if item.work_comment else ''}"
                                      f"{'<b>Work Link:</b>' + item.work_link.replace(',,,', nl) + nl * 2 if item.work_link else ''}"
                                      f"{'' if not append_file_ids else '<b>Work Photo: </b>'}", parse_mode='HTML', disable_web_page_preview=True)
            for file in append_file_ids:
                update.message.reply_photo(file)
        update.message.reply_text("Enter <b>step_id</b> which step you want to edit. (Use /canceledit to cancel)", parse_mode='HTML')
        return STEP_ENTERED


def step_entered(update, context):
    with Session() as session:
        step_id = update.message.text
        chat_data = context.chat_data
        try:
            step_id = int(step_id)
            chat_data['step_id'] = step_id
        except:
            update.message.reply_text("Only number can be passed. Please enter correct step_id")
            return
        gig_id = chat_data['gig_id']
        gig = Gig.get_gig(session=session, id=gig_id)
        try:
            global_step_to_submit = gig.steps.all()[step_id - 1].id
        except IndexError:
            update.message.reply_text(f"Step id #{step_id} does not exist. Please enter correct step_id.")
            return
        chat_data['global_id'] = global_step_to_submit
        keyboard = [
            [
                InlineKeyboardButton("Edit Comment", callback_data='editcomment'),
                InlineKeyboardButton("Edit Links", callback_data='editlinks'),
                InlineKeyboardButton("Edit Photos", callback_data='editphotos'),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Select operation using inline keyboard button.", reply_markup=reply_markup)
        return STEP_OPERATION


def change_record(update, context):
    with Session() as session:
        chat_data = context.chat_data
        query = update.callback_query
        query.answer()
        if query.data == 'editcomment':
            query.edit_message_text(text=f"Enter new comment.")
            return SELECTED_COMMENT
        elif query.data == 'editlinks':
            query.edit_message_text(text="Enter work links one by one (Use /completelinks once done).")
            return SELECTED_LINKS
        elif query.data == 'editphotos':
            query.edit_message_text(text=f"Enter new photos one by one (Use /completephotos once done).")
            return SELECTED_PHOTOS
        else:
            query.edit_message_text(text=f"Something is wrong. Try again later.")
            return END


def entered_comment(update, context):
    with Session() as session:
        comment = update.message.text
        chat_data = context.chat_data
        giguser = chat_data['giguser']
        global_id = chat_data['global_id']
        stepgiguser = StepGigUser.get_stepgiguser_by_stepid_giguserid(session=session, stepid=global_id, giguserid=giguser.id)
        if stepgiguser:
            work_comment = stepgiguser.update_comment(session=session, comment=comment)
            if work_comment:
                update.message.reply_text(f"New comment - {stepgiguser.work_comment}")
            else:
                update.reply_text("Error while updating step!")
        else:
            update.message.reply_text("Step does not exist!")
        return END


def entered_links(update, context):
    link = update.message.text
    chat_data = context.chat_data
    if not chat_data.get('work_link'):
        chat_data['work_link'] = list()
    chat_data['work_link'].append(link)
    return SELECTED_LINKS


def delete_local_links(links):
    with Session() as session:
        for link in links:
            # obj = session.query(StepGigUser).values('work_link').filter(StepGigUser.work_link == link).first()
            # fields = ["work_link"]
            # obj = session.query(map(lambda x: getattr(StepGigUser.c, x), fields)).filter(StepGigUser.work_link == link).first()
            StepGigUser.work_link = None
            # session.delete(obj)
            try:
                session.commit()
            except:
                session.rollback()
                # print("Something went wrong!")
        if links:
            return True
        else:
            return False


def complete_links(update, context):
    with Session() as session:
        chat_data = context.chat_data
        if not chat_data.get('work_link'):
            chat_data['work_links'] = None
        else:
            chat_data['work_links'] = ',,,'.join(chat_data['work_link'])
        giguser = chat_data['giguser']
        global_id = chat_data['global_id']
        stepgiguser = StepGigUser.get_stepgiguser_by_stepid_giguserid(session=session, stepid=global_id, giguserid=giguser.id)
        if stepgiguser:
            if stepgiguser.work_link:
                links = stepgiguser.work_photo.split(',,,')
            else:
                links = stepgiguser.work_photo
            deletion_status = delete_local_links(links)
            # deletion_status = delete_s3_files(photos)
            if deletion_status:
                update_links = stepgiguser.update_link(session=session, links=chat_data['work_links'])
                if update_links:
                    update.message.reply_text(f'Updated work links - {stepgiguser.work_link}')
                else:
                    update.reply_text("Error while updating links!")
            return END


# delete file and set null
def delete_local_photo_files(photos):
    with Session() as session:
        print(photos)
        for photo in photos:
            obj = session.query(StepGigUser).filter(StepGigUser.work_photo == photo).first()
            session.delete(obj)
            try:
                session.commit()
            except:
                session.rollback()
                # print("Something went wrong!")
        if photos:
            return True
        else:
            return False


# https://stackoverflow.com/questions/3140779/how-to-delete-files-from-amazon-s3-bucket
def delete_s3_files(photos):
    s3 = boto3.resource("s3")
    for photo in photos:
        bucket_source = {
            'Bucket': BUCKET_NAME,
            'Key': photo
        }
        s3.meta.client.delete(bucket_source)
        # s3 = boto3.client('s3')
        # s3.delete_object(Bucket="s3bucketname", Key="s3filepath")

        # my_bucket = s3_resource.Bucket("your_bucket_name")
        # response = my_bucket.delete_objects(
        #     Delete={
        #         'Objects': [
        #             {
        #                 'Key': "your_file_name_key"  # the_name of_your_file
        #             }
        #         ]
        #     }
        # )


def complete_photos(update, context):
    with Session() as session:
        chat_data = context.chat_data
        if not chat_data.get('work_photo'):
            chat_data['work_photos'] = None
            logger.info(f"Inside /editgigsub. /completephotos. No work photos so storing chat_data['work_photos'] to None")
        else:
            chat_data['work_photos'] = ',,,'.join(chat_data['work_photo'])
        giguser = chat_data['giguser']
        global_id = chat_data['global_id']
        stepgiguser = StepGigUser.get_stepgiguser_by_stepid_giguserid(session=session, stepid=global_id, giguserid=giguser.id)
        if stepgiguser:
            if stepgiguser.work_photo:
                photos = stepgiguser.work_photo.split(',,,')
            else:
                photos = stepgiguser.work_photo
            print(photos)
            print(chat_data['work_photos'])
            deletion_status = delete_local_photo_files(photos)
            # deletion_status = delete_s3_files(photos)
            if deletion_status:
                photos = stepgiguser.update_photo(session=session, photos=chat_data['work_photos'])
                if photos:
                    update.message.reply_text(f'Updated work photos - {stepgiguser.work_photo}')
                else:
                    update.reply_text("Error while updating photos!")
            # update.message.reply_text("One or more files couldn't be deleted")
            return END


def only_photo_accepted(update, context):
    update.message.reply_text("Only photos are accepted. Submit photo of your work for the respective step!")
    return WORKPHOTO


def entered_photos(update, context):
    update.message.reply_text("Photo received. Processing")
    our_file = update.effective_message.photo[-1]
    if our_file:
        try:
            file_id = our_file.file_id
            # file_unique_id = our_file.file_unique_id
            actual_file = our_file.get_file()

            filepath_to_download = actual_file['file_path']

            ext = filepath_to_download.split('.')[-1]
            filename_to_store = f"{file_id}.{ext}"

            logger.info(f"Inside /submitgigstep. Got photo. Saving photo as- {filename_to_store}")
            update.message.reply_chat_action(action=constants.CHATACTION_UPLOAD_PHOTO)

            # status = save_file_in_s3(filepath_to_download=filepath_to_download, bucket=BUCKET_NAME,
            # filename_to_store=filename_to_store)
            status = save_file_locally(filepath_to_download=filepath_to_download, filename_to_store=filename_to_store)
            if status:
                update.message.reply_text('Image uploaded successfully..')
            else:
                update.message.reply_text("Image not uploaded. Plz try again")
                return END
            chat_data = context.chat_data
            if not chat_data.get('work_photo'):
                chat_data['work_photo'] = list()
            final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
            chat_data['work_photo'].append(final_file_path)
            logger.info(f"Inside /submitgigstep. Got photo. Final work photos - {chat_data['work_photo']}")
        except:
            logger.error(f"Update {update} caused error WHILE SAVING PHOTO- {context.error}")
            logger.error(f"Exception while saving photo", exc_info=True)
    update.message.reply_text('Photo processed, successfully!')
    return SELECTED_PHOTOS


def timeout_submitgigstep(update, context):
    with Session() as session:
        update.message.reply_text(
            f'Timeout. Again, use /submitgigstep to submit step of gig. (Timeout limit - {submitgigstep_timeout_time} sec)')
        chat_data = context.chat_data
        chat_data.clear()
        logger.info(f"Timeout for /submitgigstep")
        return END


def timeout_checkgigusersub(update, context):
    with Session() as session:
        update.message.reply_text(
            f'Timeout. Again, use /checkgigusersub to check sumission of gig users. (Timeout limit - {addgig_timeout_time} sec)')
        chat_data = context.chat_data
        chat_data.clear()
        logger.info(f"Timeout for /checkgigusersub")
        return END


def timeout_addgig(update, context):
    with Session() as session:
        update.message.reply_text(
            f'Timeout. Again, use /addgig to submit step of gig. (Timeout limit - {addgig_timeout_time} sec)')
        chat_data = context.chat_data
        chat_data.clear()
        logger.info(f"Timeout for /addgig")
        return END


def anyrandom(update, context):
    update.message.reply_text("Sorry, I am new to understand this!")


def error(update, context: CallbackContext):
    logger.warning(f'Update {update} caused an error {context.error}')


def set_bot_commands(updater):
    commands = [BotCommand(key, val) for key, val in dict(suggested_commands).items()]
    updater.bot.set_my_commands(commands)


def print_all_tables():
    with Session() as session:
        print([user for user in session.query(User).all()])
        print([gig for gig in session.query(Gig).all()])
        print([step for step in session.query(Step).all()])
        print([giguser for giguser in session.query(GigUser).all()])
        print([stepgiguser for stepgiguser in session.query(StepGigUser).all()])


if __name__ == '__main__':
    User.__table__.create(engine, checkfirst=True)
    Gig.__table__.create(engine, checkfirst=True)
    Step.__table__.create(engine, checkfirst=True)
    GigUser.__table__.create(engine, checkfirst=True)
    StepGigUser.__table__.create(engine, checkfirst=True)
    # print_all_tables()

    updater = Updater(token='2098863676:AAFJHIw5MkNnWePBzSQAMFTYrKWCCXsgplg', use_context=True)
    set_bot_commands(updater)
    dp: Dispatcher = updater.dispatcher

    select_option_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_option, pattern='^editdescription|editsteps|editinstructions$')],
        states={
            SELECTED_DESCRIPTION: [MessageHandler(Filters.text and ~Filters.command, selected_description)],
            SELECTED_STEPS: [MessageHandler(Filters.text and ~Filters.command, selected_steps)],
            STEP_EDITION: [MessageHandler(Filters.text and ~Filters.command, step_edition)],
            SELECTED_INSTRUCTIONS: [MessageHandler(Filters.text and ~Filters.command, selected_instructions)]
        },
        fallbacks=[CommandHandler('canceledit', canceledit)],
        map_to_parent={
            END: END
        }
    )

    editgig_handler = ConversationHandler(
        entry_points=[CommandHandler('editgig', editgig)],
        states={
            SELECTED_OPTION: [select_option_handler]
        },
        fallbacks=[CommandHandler('canceledit', canceledit)],
    )

    checksubwithgigid_handle = ConversationHandler(
        entry_points=[CommandHandler('checkgigusersub', checkgigusersub)],
        states={
            SELECTED_USER: [MessageHandler(Filters.text and ~Filters.command, selected_user)],
            STEP_REVIEW: [MessageHandler(Filters.text and ~Filters.command, review_step)],
            REVIEW: [MessageHandler(Filters.text and ~Filters.command, review)],
            ConversationHandler.TIMEOUT: [MessageHandler(Filters.text | Filters.command, timeout_checkgigusersub)]
        },
        fallbacks=[CommandHandler('cancelprocess', cancelprocess)],
        conversation_timeout=checkgigusersub_timeout_time
    )

    gig_create_handler = ConversationHandler(
        entry_points=[CommandHandler('addgig', addgig)],
        states={
        DESC: [MessageHandler(Filters.text and ~Filters.command, desc_of_new_gig)],
        STEPS: [MessageHandler(Filters.text and ~Filters.command, steps_of_new_gig),
                CommandHandler('stepdone', done_with_steps)],
        INSTRUCTIONS: [MessageHandler(Filters.text and ~Filters.command, instructions_of_new_gig)],
        ConversationHandler.TIMEOUT: [MessageHandler(Filters.text | Filters.command, timeout_addgig)]
        },
        fallbacks=[CommandHandler('newgigcancel', newgigcancel)],
        conversation_timeout=addgig_timeout_time
    )

    submit_gig_handler = ConversationHandler(
        entry_points=[CommandHandler('submitgigstep', submitgigstep)],
        states={
            WORKCOMMENT: [CommandHandler('skipcomment', skipcomment),
                          MessageHandler(Filters.text and ~Filters.command, submit_work_comment)],
            WORKLINK: [CommandHandler('donelinks', donelinks),
                       MessageHandler(Filters.text and ~Filters.command, submit_work_link)],
            WORKPHOTO: [CommandHandler('donephotos', donephotos),
                        MessageHandler(Filters.photo, submit_work_photo),
                        MessageHandler(Filters.text, no_text_allowed),
                        ],
            ConversationHandler.TIMEOUT: [MessageHandler(Filters.text | Filters.command, timeout_submitgigstep)]
        },
        fallbacks=[CommandHandler('cancelsubmission', cancelsubmission)],
        conversation_timeout=submitgigstep_timeout_time
    )

    edit_record_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(change_record, pattern='^editcomment|editlinks|editphotos$')],
        states={
            SELECTED_COMMENT: [MessageHandler(Filters.text and ~Filters.command, entered_comment)],
            SELECTED_LINKS: [CommandHandler('completelinks', complete_links),
                            MessageHandler(Filters.text and ~Filters.command, entered_links)],
            SELECTED_PHOTOS: [CommandHandler('completephotos', complete_photos),
                              MessageHandler(Filters.photo, entered_photos),
                              MessageHandler(Filters.text, only_photo_accepted)]
        },
        fallbacks=[CommandHandler('canceledit', canceledit)],
        map_to_parent={
            END: END
        }
    )

    editgigsub_handler = ConversationHandler(
        entry_points=[CommandHandler('editgigsub', editgigsub)],
        states={
            STEP_ENTERED: [MessageHandler(Filters.text and ~Filters.command, step_entered)],
            STEP_OPERATION: [edit_record_handler]
            # DELETE_GIG :
        },
        fallbacks=[CommandHandler('canceledit', canceledit)],
    )

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('help', help))
    dp.add_handler(CommandHandler('allgigs', allgigs))
    dp.add_handler(CommandHandler('giginfo', giginfo))
    dp.add_handler(CommandHandler('mygigs', mygigs))
    dp.add_handler(CommandHandler('takegig', takegig))
    dp.add_handler(CommandHandler('checkgigsub', checkgigsub))
    dp.add_handler(submit_gig_handler)
    dp.add_handler(editgigsub_handler)


    # Admin only commands
    dp.add_handler(gig_create_handler)
    dp.add_handler(editgig_handler)
    # dp.add_handler()
    dp.add_handler(CommandHandler('deletegig', deletegig))
    dp.add_handler(checksubwithgigid_handle)
    dp.add_handler(CommandHandler('checksubwithgiguserid', checksubwithgiguserid))

    dp.add_error_handler(error)
    dp.add_handler(MessageHandler(Filters.text, anyrandom))
    mode = os.environ.get("MODE", "polling")

    if mode == 'webhook':
        SSL_CERT = 'ssl-certi/ctogigs-tgbot-ssl.pem'
        live_server_url = os.environ.get("LIVE_SERVER_URL", "0.0.0.0")
        logger.info('inside WEBHOOK block')
        updater.start_webhook(listen="0.0.0.0", port=8443, url_path=f"{TOKEN}",
                              webhook_url=f"{live_server_url}/{TOKEN}", cert=SSL_CERT)
        # updater.bot.setWebhook(f"{live_server_url}/{TOKEN}", certificate=SSL_CERT)
        logging.info(updater.bot.get_webhook_info())
    else:
        logger.info('inside POLLING block')
        updater.start_polling()
        updater.idle()






# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


# from telegram import constants, InlineKeyboardButton, InlineKeyboardMarkup
# from telegram.ext import Updater, Dispatcher, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
# from models import User, Gig, Step, GigUser, StepGigUser
# from dbhelper import Session, engine
# from datetime import datetime
# import logging
# import boto3
# import os
# from dotenv import load_dotenv
# import requests
# from botocore.exceptions import NoCredentialsError
# from telegram.bot import BotCommand
# from bot_commands import suggested_commands
#
# load_dotenv()
#
# log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# logging.basicConfig(format=log_format, level=logging.INFO)
# logger = logging.getLogger(__name__)
#
# # TOKEN = os.getenv('CTOGIGS_TELEGRAM_TOKEN')
# TOKEN = '2098863676:AAFJHIw5MkNnWePBzSQAMFTYrKWCCXsgplg'
# show_all_gigs_limit = 5
# DESC, STEPS, INSTRUCTIONS = range(3)
# WORKCOMMENT, WORKLINK, WORKPHOTO = range(3)
# SELECTED_OPTION, SELECTED_DESCRIPTION, SELECTED_STEPS, STEP_EDITION, SELECTED_INSTRUCTIONS = range(5)
# SELECTED_USER, STEP_REVIEW, REVIEW = range(3)
# STEP_ENTERED, STEP_OPERATION, SELECTED_COMMENT, SELECTED_LINKS, SELECTED_PHOTOS = range(5)
# # ADMIN_CHAT_IDS = [1031241092]
# ADMIN_CHAT_IDS = [1066103338]     # Mine
#
# submitgig_timeout_time = 120
# addnewgig_timeout_time = 120
#
# FOLDERNAME_USERWORKS = 'userworks/'
# if not os.path.isdir(FOLDERNAME_USERWORKS):
#     os.mkdir(FOLDERNAME_USERWORKS)
#
# BUCKET_NAME = 'work-photos-ctogigsbot'
#
#
# def save_file_in_s3(filepath_to_download, bucket, filename_to_store):
#     s3 = boto3.client('s3', region_name='us-east-1')
#     # print(type(s3))
#     try:
#         logger.info(f"Inside /addlog. Saving image on S3")
#         imageResponse = requests.get(filepath_to_download, stream=True).raw
#         final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
#         s3.upload_fileobj(imageResponse, bucket, final_file_path)
#         logger.info("Image Saved on S3..")
#         return True
#     except FileNotFoundError:
#         logger.error('File not found..')
#         return False
#     except NoCredentialsError:
#         logger.info('Credentials not available')
#         return False
#     except:
#         logger.info('Some other error saving the file to S3')
#
#
# def start(update, context):
#     logging.info('Inside start')
#     first_name = update.message.from_user.first_name
#     last_name = update.message.from_user.last_name
#     chat_id = update.message.chat_id
#     tg_username = None
#     if update.message.from_user.username:
#         tg_username = update.message.from_user.username
#     created_at = datetime.now()
#     with Session() as session:
#         user = User.get_user_by_chatid(session=session, chat_id=chat_id)
#         if not user:
#             user = User(chat_id=chat_id, first_name=first_name, last_name=last_name, tg_username=tg_username,
#                         created_at=created_at)
#             session.add(user)
#             try:
#                 session.commit()
#                 update.message.reply_text(f"Welcome to CTOlogs, {user.first_name.title()}")
#             except:
#                 session.rollback()
#         else:
#             update.message.reply_text(f"Welcome back, {user.first_name.title()}")
#
#
# def help(update, context):
#     update.message.reply_text('This bot allows you to explore and register for <b><i>python/fullstack/ml-dl-nlp/blockchain</i></b> related gigs. '
#                               '\n\nUse / to see list of all supported/usable commands!', parse_mode='HTML')
#
#
# def gigs(update, context):
#     with Session() as session:
#         user = get_current_user(session=session, update=update)
#         if not user:
#             return
#         all_gigs = session.query(Gig).order_by(Gig.created_at.desc()).limit(show_all_gigs_limit).all()
#         if not all_gigs:
#             update.message.reply_text("Gig not created yet!")
#             return
#         update.message.reply_text(f'Showing latest {show_all_gigs_limit} gigs\n'
#                                   f"Use <i>/giginfo 3</i> to check gig with 3", parse_mode='HTML')
#         for gig in all_gigs:
#             nl = '\n\n'
#             final_steps = nl.join([f"{_id+1}. {step.step_text}" for _id, step in enumerate(gig.steps.all())])
#             update.message.reply_text(f"<b>Gig Id:</b> {gig.id}\n\n"
#                                       f"<b>Desc:</b> {gig.short_description}\n\n"
#                                       f"<b>Steps:</b> \n{final_steps}\n\n"
#                                       f"<b>Instructions:</b> {gig.instructions}", parse_mode='HTML')
#
#
# def takegig(update, context):
#     with Session() as session:
#         current_user = get_current_user(update=update, session=session)
#         if not current_user:
#             return
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                      '<i>e.g. /takegig 1 or /takegig 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#
#         current_gig = Gig.get_gig(session=session, id=recv_id)
#         if not current_gig:
#             update.message.reply_text('Such a gig does not exist!')
#             return
#         current_user.gigusers.append(GigUser(gig_id=recv_id))
#         session.add(current_user)
#         try:
#             session.commit()
#         except:
#             session.rollback()
#             update.message.reply_text('Something went wrong. Please try again!')
#             return
#         else:
#             update.message.reply_text(f'You have signed up for Gig {recv_id}.\n'
#                                       f' Check /mygigs for details.')
#
#
# def giginfo(update, context):
#     with Session() as session:
#         user = get_current_user(session=session, update=update)
#         if not user:
#             return
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                       '<i>e.g. /giginfo 1 or /giginfo 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text(f"Gig with id - {recv_id} does not exist")
#         else:
#             nl = '\n\n'
#             final_steps = nl.join([f"{_id + 1}. {step.step_text}" for _id, step in enumerate(gig.steps.all())])
#             update.message.reply_text(f"<b>Gig Id:</b> {gig.id}\n\n"
#                                       f"<b>Desc:</b> {gig.short_description}\n\n"
#                                       f"<b>Steps:</b> \n{final_steps}\n\n"
#                                       f"<b>Instructions:</b> {gig.instructions}", parse_mode='HTML')
#
#
# def mygigs(update, context):
#     with Session() as session:
#         current_user = get_current_user(session=session, update=update)
#         if not current_user:
#             return
#         nl = '\n\n'
#         if not current_user.gigs:
#             update.message.reply_text("You haven't taken up any gigs yet!")
#             return
#         update.message.reply_text('You have registered for the following gigs')
#         for gig in current_user.gigs:
#             update.message.reply_text(f"Gig Id: {gig.id}\n\n"
#                                       f"Desc: {gig.short_description}\n\n"
#                                       f"Steps:\n{nl.join([step.step_text for step in gig.steps.all()])}")
#
#
# def addnewgig(update, context):
#     chat_id = update.message.chat_id
#     if chat_id not in ADMIN_CHAT_IDS:
#         update.message.reply_text('You do not have access to do this command')
#         return
#     update.message.reply_text("Alright, let's add a new gig. Write description in short.\n"
#                               "Use /newgigcancel to cancel.")
#     return DESC
#
#
# def desc_of_new_gig(update, context: CallbackContext):
#     description = update.message.text
#     chat_data = context.chat_data
#     chat_data['desc'] = description
#     update.message.reply_text("Got the description. Write steps one by one.\n"
#                               "Use /stepdone when done.")
#     return STEPS
#
#
# def steps_of_new_gig(update, context):
#     steps = update.message.text
#     chat_data = context.chat_data
#     if not chat_data.get('steps'):
#         chat_data['steps'] = list()
#     chat_data['steps'].append(steps)
#     return STEPS
#
#
# def done_with_steps(update, context):
#     update.message.reply_text("Noted the steps. Any instructions?")
#     return INSTRUCTIONS
#
#
# def instructions_of_new_gig(update, context):
#     instructions = update.message.text
#     update.message.reply_text("That's it!")
#     chat_data = context.chat_data
#     chat_data['instructions'] = instructions
#     save_new_gig(update, context)
#     return ConversationHandler.END
#
#
# def save_new_gig(update, context):
#     chat_id = update.message.chat_id
#     chat_data = context.chat_data
#     short_description = chat_data['desc']
#     instructions = chat_data['instructions']
#     steps = chat_data['steps']
#     owner_chat_id = chat_id
#     gig = Gig(short_description=short_description, instructions=instructions, owner_chat_id=owner_chat_id, created_at=datetime.now(), updated_at=datetime.now())
#     with Session() as session:
#         session.add(gig)
#         try:
#             session.commit()
#             update.message.reply_text(f'Gig created, {gig}')
#         except:
#             session.rollback()
#         for localstepid, step in enumerate(steps):
#             step_obj = Step(localstepid=localstepid + 1, gig_id=gig.id, step_text=step)
#             session.add(step_obj)
#         try:
#             session.commit()
#             chat_data.clear()
#             logger.info('chat_data cleared')
#         except:
#             session.rollback()
#
#
# def newgigcancel(update, context):
#     update.message.reply_text("Cancelled adding new gig")
#     chat_data = context.chat_data
#     chat_data.clear()
#     return ConversationHandler.END
#
#
# def anyrandom(update, context):
#     update.message.reply_text("Sorry, I am new to understand this!")
#
#
# def error(update, context: CallbackContext):
#     logger.warning(f'Update {update} caused an error {context.error}')
#
#
# def print_all_tables():
#     with Session() as session:
#         print([user for user in session.query(User).all()])
#         print([gig for gig in session.query(Gig).all()])
#         print([step for step in session.query(Step).all()])
#         print([giguser for giguser in session.query(GigUser).all()])
#         print([stepgiguser for stepgiguser in session.query(StepGigUser).all()])
#
#
# def get_current_user(session, update):
#     chat_id = update.message.chat_id
#     user = User.get_user_by_chatid(session=session, chat_id=chat_id)
#     if user:
#         return user
#     else:
#         update.message.reply_text('Use /start first then use this command again!')
#         return None
#
#
# def save_file_locally(filepath_to_download, filename_to_store):
#     response = requests.get(filepath_to_download)
#     final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
#     try:
#         logger.info(f"Inside /addlog. Saving image locally")
#         with open(final_file_path, 'wb') as f:
#             f.write(response.content)
#         logger.info("Image Saved locally..")
#         return True
#     except:
#         logger.info("Image could not be saved locally..")
#         return False
#
#
# def submitgig(update, context):
#     with Session() as session:
#         user = get_current_user(session=session, update=update)
#         if not user:
#             return
#         if not context.args:
#             update.message.reply_text("You need to pass gig_id next to the command.")
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number is allowed next to the command.')
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text("This is not a valid gig!")
#             return
#         giguser = GigUser.get_giguser_by_gigid_userid(session=session, userid=user.id, gigid=gig.id)
#         if not giguser:
#             update.message.reply_text(f"You need to TAKE this gig first. Use '/takegig {gig.id}' to register for that gig!")
#             return
#         # update.message.reply_text(f"Alright, accepting your work for Gig #{recv_id} \n(Use /cancelsubmission to cancel.)")
#         steps_submitted = giguser.stepgigusers.all()
#         global_step_to_submit = gig.steps.all()[0].id
#         local_step_to_submit = gig.steps.filter(Step.id == global_step_to_submit).first().localstepid
#
#         if not steps_submitted and local_step_to_submit == 1:
#             update.message.reply_text(
#                 f'Accepting your work for <b>Step {local_step_to_submit} (global step id {global_step_to_submit})</b> of <b>Gig {recv_id}</b>\n'
#                 f'(Use /cancelsubmission to cancel submission of step.)\n\n'
#                 f'This is FIRST STEP for which you are submitting your work!\n'
#                 f'Write comment if any, /skipcomment to skip.\n', parse_mode='HTML')
#         else:
#             steps_submitted_list = [stepgiguser.step_id for stepgiguser in steps_submitted]
#             last_step_submitted = max(steps_submitted_list)
#             last_step_of_gig = gig.steps.all()[-1].id
#             if last_step_submitted == last_step_of_gig:
#                 update.message.reply_text("You have submitted all the steps! No more steps left. Your gig submission is complete!")
#                 return
#             elif last_step_submitted < last_step_of_gig:
#                 global_step_to_submit = max(steps_submitted_list) + 1
#                 update.message.reply_text(f"You have already submitted your work for step #{local_step_to_submit} (global step id #{global_step_to_submit - 1})!\n"
#                                       f"(Use /cancelsubmission to cancel.)\n\n"
#                                       f"Submit your work for {local_step_to_submit + 1} (global step id {global_step_to_submit}) step now.\n"
#                                       f"Write comment if any, /skipcomment to skip.")
#
#         chat_data = context.chat_data
#         chat_data['giguser_id'] = giguser.id
#         chat_data['global_step_to_submit'] = global_step_to_submit
#         # local_step_to_submit = Gig.get_gig(session=session, id=global_step_to_submit).localstepid
#     return WORKCOMMENT
#
#
# def submit_work_comment(update, context):
#     chat_data = context.chat_data
#     work_comment = update.message.text
#     chat_data['work_comment'] = work_comment
#     update.message.reply_text("Got your comment.\n"
#                               "Share github/drive/youtube link that points to your code or video demonstration of the step/code.\n"
#                               "Use /donelinks once done")
#     return WORKLINK
#
#
# def submit_work_link(update, context):
#     link = update.message.text
#     chat_data = context.chat_data
#     if not chat_data.get('work_link_temp'):
#         chat_data['work_link_temp'] = list()
#     chat_data['work_link_temp'].append(link)
#     return WORKLINK
#
#
# def submit_work_photo(update, context):
#     update.message.reply_text("Photo received. Processing")
#     our_file = update.effective_message.photo[-1]
#     if our_file:
#         try:
#             file_id = our_file.file_id
#             # file_unique_id = our_file.file_unique_id
#             actual_file = our_file.get_file()
#
#             filepath_to_download = actual_file['file_path']
#
#             ext = filepath_to_download.split('.')[-1]
#             filename_to_store = f"{file_id}.{ext}"
#
#             logger.info(f"Inside /submitgig. Got photo. Saving photo as- {filename_to_store}")
#             update.message.reply_chat_action(action=constants.CHATACTION_UPLOAD_PHOTO)
#
#             # status = save_file_in_s3(filepath_to_download=filepath_to_download, bucket=BUCKET_NAME,
#             # filename_to_store=filename_to_store)
#             status = save_file_locally(filepath_to_download=filepath_to_download, filename_to_store=filename_to_store)
#             if status:
#                 update.message.reply_text('Image uploaded successfully..')
#             else:
#                 update.message.reply_text("Image not uploaded. Plz try again")
#
#             chat_data = context.chat_data
#             if not chat_data.get('work_photo_temp'):
#                 chat_data['work_photo_temp'] = list()
#             final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
#             chat_data['work_photo_temp'].append(final_file_path)
#             logger.info(f"Inside /submitgig. Got photo. Final work photos - {chat_data['work_photo_temp']}")
#         except:
#             logger.error(f"Update {update} caused error WHILE SAVING PHOTO- {context.error}")
#             logger.error(f"Exception while saving photo", exc_info=True)
#     update.message.reply_text('Photo processed, successfully!')
#     return WORKPHOTO
#
#
# def skipcomment(update, context):
#     update.message.reply_text('Skipping comment.')
#     chat_data = context.chat_data
#     chat_data['work_comment'] = None
#     update.message.reply_text("Share github/drive/youtube link that points to your code or video demonstration of the step/code.\n"
#                               "Use /donelinks once done")
#     return WORKLINK
#
#
# def no_text_allowed(update, context):
#     update.message.reply_text("Only photos are accepted. Submit photo of your work for the respective step!")
#     return WORKPHOTO
#
#
# def donelinks(update, context):
#     chat_data = context.chat_data
#     if not chat_data.get('work_link_temp'):
#         chat_data['work_links'] = None
#     else:
#         chat_data['work_links'] = ',,,'.join(chat_data['work_link_temp'])
#     update.message.reply_text('Next, upload photos of code/output if any.\n'
#                         'Use /donephotos once done')
#     return WORKPHOTO
#
#
# def donephotos(update, context):
#     chat_data = context.chat_data
#     if not chat_data.get('work_photo_temp'):
#         chat_data['work_photos'] = None
#         logger.info(f"Inside /submitgig. /donephotos. No work photos so storing chat_data['work_photos'] to None")
#     else:
#         chat_data['work_photos'] = ',,,'.join(chat_data['work_photo_temp'])  # deliberately using this instead of comma, bcz if user somehow enters , in his work links, then it'll be split unnecessarily. so we want some unique identifier.
#
#     status = save_gig_submission(update, context)
#     if status:
#         update.message.reply_text('Submitted the gig successfully.\n'
#                         'Check /mygigwithans for more details.')
#     else:
#         update.message.reply_text("Something went wrong. Please submit the work for this step again.")
#     return ConversationHandler.END
#
#
# def cancelsubmission(update, context):
#     update.message.reply_text('Gig submission cancelled.')
#     return ConversationHandler.END
#
#
# def save_gig_submission(update, context):
#     chat_data = context.chat_data
#     giguser_id = chat_data['giguser_id']
#     step_id = chat_data['global_step_to_submit']
#     work_comment = chat_data['work_comment']
#     work_links = chat_data['work_links']
#     work_photos = chat_data['work_photos']
#     update.message.reply_text('Alright. Saving your record')
#
#     stepgiguser = StepGigUser(step_id=step_id, giguser_id=giguser_id, work_comment=work_comment, work_photo=work_photos, work_link=work_links, submitted_at=datetime.now())
#     with Session() as session:
#         session.add(stepgiguser)
#         try:
#             session.commit()
#             update.message.reply_text(f'StepGigUser created, {stepgiguser}', disable_web_page_preview=True)
#             chat_data.clear()
#             logger.info('chat_data cleared')
#         except:
#             update.message.reply_text("Something went wrong")
#             session.rollback()
#     return True
#
#
# def mygigwithans(update, context):
#     with Session() as session:
#         user: User = get_current_user(session=session, update=update)
#         if not user:
#             return
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                       '<i>e.g. /mygigwithans 1 or /mygigwithans 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text(f"Gig with id - {recv_id} does not exist")
#             return
#         giguser = GigUser.get_giguser_by_gigid_userid(session=session, gigid=gig.id, userid=user.id)
#         if not giguser:
#             update.message.reply_text(f"You need to TAKE this gig first. Use '/takegig {gig.id}' to register for that gig!")
#             return
#         for _id, item in enumerate(giguser.stepgigusers.all()):
#             append_file_ids = []
#             if item.work_photo:
#                 photos = item.work_photo.split(',,,')
#                 for photo in photos:
#                     if photo.find('userworks/') != -1:
#                         file_id = photo.split('userworks/')[-1].split('.')[0]
#                         append_file_ids.append(file_id)
#             nl = '\n'
#             update.message.reply_text(f"<b>Step Id:</b> {_id + 1}\n\n"
#                                       f"<b>Submitted at:</b> {item.submitted_at.strftime('%d %b %Y, %I:%M %p') if item.submitted_at else ''}\n\n"
#                                       f"<b>Review:</b> {item.review}{nl * 2}"
#                                       f"<b>Reviewed at:</b> {item.reviewed_at.strftime('%d %b %Y, %I:%M %p')}{nl*2}"
#                                       f"{'<b>Work Comment:</b>' + item.work_comment + nl * 2 if item.work_comment else ''}"
#                                       f"{'<b>Work Link:</b>' + item.work_link.replace(',,,', nl) + nl * 2 if item.work_link else ''}"
#                                       f"{'' if not append_file_ids else '<b>Work Photo: </b>'}", parse_mode='HTML', disable_web_page_preview=True)
#             for file in append_file_ids:
#                 update.message.reply_photo(file)
#
#
# def set_bot_commands(updater):
#     commands = [BotCommand(key, val) for key, val in dict(suggested_commands).items()]
#     updater.bot.set_my_commands(commands)
#
#
# def timeout_submitgig(update, context):
#     with Session() as session:
#         update.message.reply_text(f'Timeout. Use /submitgig again to submit step of gig. (Timeout limit - {submitgig_timeout_time} sec)')
#         chat_data = context.chat_data
#         chat_data.clear()
#         logger.info(f"Timeout for /submitgig")
#         return ConversationHandler.END
#
#
# def timeout_addnewgig(update, context):
#     with Session() as session:
#         update.message.reply_text(f'Timeout. Use /addnewgig again to submit step of gig. (Timeout limit - {addnewgig_timeout_time} sec)')
#         chat_data = context.chat_data
#         chat_data.clear()
#         logger.info(f"Timeout for /addnewgig")
#         return ConversationHandler.END
#
#
# def editgig(update, context):
#     chat_data = context.chat_data
#     chat_id = update.message.chat_id
#     if chat_id not in ADMIN_CHAT_IDS:
#         update.message.reply_text('You do not have access to do this command')
#         return
#     with Session() as session:
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                       '<i>e.g. /editgig 1 or /editgig 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#             chat_data['recv_id'] = recv_id
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text(f"Gig with id - {recv_id} does not exist")
#             return
#         else:
#             keyboard = [
#                 [
#                     InlineKeyboardButton("Edit Description", callback_data='editdescription'),
#                     InlineKeyboardButton("Edit Steps", callback_data='editsteps'),
#                     InlineKeyboardButton("Edit Instructions", callback_data='editinstructions'),
#                 ]
#             ]
#             reply_markup = InlineKeyboardMarkup(keyboard)
#             update.message.reply_text(f"Gig #{recv_id} details are shown below:\n\n{gig}", reply_markup=reply_markup)
#             return SELECTED_OPTION
#
#
# def edit_option(update, context):
#     with Session() as session:
#         chat_data = context.chat_data
#         gig = Gig.get_gig(session=session, id=chat_data['recv_id'])
#         if not gig:
#             return
#         query = update.callback_query
#         query.answer()
#         if query.data == 'editdescription':
#             query.edit_message_text(text=f"Enter new description (/canceledit to cancel)")
#             return SELECTED_DESCRIPTION
#         elif query.data == 'editsteps':
#             chat_data = context.chat_data
#             recv_id = chat_data['recv_id']
#             nl = '\n\n'
#             query.edit_message_text(text=f"Enter step id which you want to edit.{nl}The steps of gig #{recv_id} are given below:\n{nl.join([f'{_id + 1}. {step.step_text}' for _id, step in enumerate(gig.steps.all())])}")
#             return SELECTED_STEPS
#         elif query.data == 'editinstructions':
#             query.edit_message_text(text=f"Enter new instructions (/canceledit to cancel)")
#             return SELECTED_INSTRUCTIONS
#         else:
#             query.edit_message_text(text=f"Something is wrong. Try again later.")
#             return ConversationHandler.END
#
#
# def checksubwithgigid(update, context):
#     chat_id = update.message.chat_id
#     if chat_id not in ADMIN_CHAT_IDS:
#         update.message.reply_text('You do not have access to do this command')
#         return
#     with Session() as session:
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                       '<i>e.g. /checksubwithgigid 1 or /checksubwithgigid 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#             chat_data = context.chat_data
#             chat_data['gig_id'] = recv_id
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         user = get_current_user(session=session, update=update)
#         if not user:
#             update.message.reply_text("First use /start command.")
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text(f"Gig with id - {recv_id} does not exist")
#             return
#         giguser = GigUser.get_giguser_by_gigid_userid(session=session, gigid=recv_id, userid=user.id)
#
#         if not giguser:
#             update.message.text(f"You haven't take gig #{recv_id}. You can take gig using command '/takegig {recv_id}.'")
#             return
#         nl = '\n\n'
#         update.message.reply_text("Enter user id")
#         update.message.reply_text(f"List of users who taken gig #{recv_id} is given below:{nl}{nl.join([f'{item.id}. {item.first_name} {item.last_name}' for item in gig.users])}")
#         return SELECTED_USER
#
#
# def checksubwithgiguserid(update, context):
#     chat_id = update.message.chat_id
#     if chat_id not in ADMIN_CHAT_IDS:
#         update.message.reply_text('You do not have access to do this command')
#         return
#     with Session() as session:
#         if not context.args:
#             update.message.reply_text('You need to pass giguser id next to the command.\n'
#                                       '<i>e.g. /checksubwithgiguserid 1 or /checksubwithgiguserid 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         giguser = GigUser.get_giguser_by_id(session=session, id=recv_id)
#         if not giguser:
#             update.message.reply_text(f"Giguser id #{recv_id} not present!")
#             return
#         user = giguser.user
#         user_first_name = user.first_name
#         user_last_name = user.last_name
#         update.message.reply_text(f"Submission of gig #{giguser.gig_id} for user {user_first_name} {user_last_name}is given below:\n\n")
#         for _id, item in enumerate(giguser.stepgigusers.filter(StepGigUser.giguser_id == recv_id).all()):
#             append_file_ids = []
#             if item.work_photo:
#                 photos = item.work_photo.split(',,,')
#                 for photo in photos:
#                     if photo.find('userworks/') != -1:
#                         file_id = photo.split('userworks/')[-1].split('.')[0]
#                         append_file_ids.append(file_id)
#             nl = '\n'
#             update.message.reply_text(f"<b>Step Id:</b> {_id + 1}\n\n"
#                                       f"<b>Submitted at:</b> {item.submitted_at.strftime('%d %b %Y, %I:%M %p') if item.submitted_at else ''}\n\n"
#                                       f"{'<b>Work Comment:</b>' + item.work_comment + nl * 2 if item.work_comment else ''}"
#                                       f"{'<b>Work Link:</b>' + item.work_link.replace(',,,', nl) + nl * 2 if item.work_link else ''}"
#                                       f"{'' if not append_file_ids else '<b>Work Photo: </b>'}", parse_mode='HTML', disable_web_page_preview=True)
#             for file in append_file_ids:
#                 update.message.reply_photo(file)
#
#
# def selected_user(update, context):
#     with Session() as session:
#         user_id = update.message.text
#         try:
#             user_id = int(user_id)
#         except:
#             update.message.reply_text("Only numbers can be passed.")
#             return
#         user = User.get_user_by_id(session=session, id=user_id)
#         if not user:
#             update.message.reply_text(f"User id does not exist!")
#             return
#         chat_data = context.chat_data
#         chat_data['user_id'] = user_id
#         gig_id = chat_data['gig_id']
#         giguser = GigUser.get_giguser_by_gigid_userid(session=session, gigid=gig_id, userid=user_id)
#         chat_data['giguser_id'] = giguser.id
#         for _id, step in enumerate(giguser.stepgigusers.filter(StepGigUser.giguser_id == giguser.id).all()):
#             append_file_ids = []
#             if step.work_photo:
#                 photos = step.work_photo.split(',,,')
#                 for photo in photos:
#                     if photo.find('userworks/') != -1:
#                         file_id = photo.split('userworks/')[-1].split('.')[0]
#                         append_file_ids.append(file_id)
#             nl = '\n\n'
#             update.message.reply_text(f"<b>Step Id:</b> {_id +1 if step.step_id else ''}{nl}"
#                                       f"{'<b>Work Comment:</b> ' + step.work_comment if step.work_comment else ''}{nl}"
#                                       f"{'' if not step.work_photo else '<b>Work Photo:</b> '}", parse_mode='HTML', disable_web_page_preview=True)
#             for file in append_file_ids:
#                 update.message.reply_photo(file)
#         update.message.reply_text("Enter step id which you want to give review if any. (Use /cancelprocess to cancel)")
#         return STEP_REVIEW
#
#
# def selected_description(update, context):
#     with Session() as session:
#         description = update.message.text
#         chat_data = context.chat_data
#         gig = Gig.get_gig(session=session, id=chat_data['recv_id'])
#         if gig:
#             description = gig.update_description(session=session, description=description)
#             update.message.reply_text(f"New description - {description.short_description}")
#         return ConversationHandler.END
#
#
# def canceledit(update, context):
#     update.message.reply_text("Editing Cancelled!")
#     chat_data = context.chat_data
#     chat_data.clear()
#     return ConversationHandler.END
#
#
# def selected_steps(update, context):
#     step_id = update.message.text
#     try:
#         step_id = int(step_id)
#     except:
#         update.message.reply_text("Step id must be integer.")
#     chat_data = context.chat_data
#     chat_data['step_id'] = step_id
#     update.message.reply_text("Write step (use /canceledit to cancel)")
#     return STEP_EDITION
#
#
# def step_edition(update, context):
#     with Session() as session:
#         step_text = update.message.text
#         chat_data = context.chat_data
#         gig = Gig.get_gig(session=session, id=chat_data['recv_id'])
#         step_id = chat_data['step_id']
#         # nl.join([f'{_id + 1}. {step.step_text}' for _id, step in enumerate(gig.steps.all())])
#         step = gig.steps.filter(Step.localstepid == step_id).first()
#         if step:
#             step.update_step(session=session, step_text=step_text)
#             update.message.reply_text(f"Updated step - {step.step_text}")
#             return ConversationHandler.END
#         else:
#             update.message.reply_text("Step id not present!")
#             return ConversationHandler.END
#
#
# def selected_instructions(update, context):
#     with Session() as session:
#         chat_data = context.chat_data
#         instructions = update.message.text
#         gig = Gig.get_gig(session=session, id=chat_data['recv_id'])
#         if gig:
#             instruction = gig.update_instructions(session=session, instructions=instructions)
#             update.message.reply_text(f"New instructions - {instruction.instructions}")
#         return ConversationHandler.END
#
#
# def review(update, context):
#     with Session() as session:
#         chat_data = context.chat_data
#         giguser_id = chat_data['giguser_id']
#         global_id = chat_data['global_id']
#         print(global_id)
#         step_id = chat_data['step_id']
#         review = update.message.text
#         data = StepGigUser.get_stepgiguser_by_stepid_giguserid(session=session, stepid=global_id, giguserid=giguser_id)
#         if data:
#             updated_review = data.update_review(session=session, review=review)
#             update.message.reply_text(f"Updated review - {updated_review.review}\n\n")
#             return ConversationHandler.END
#         else:
#             update.message.reply_text("Something went wrong!")
#             return ConversationHandler.END
#
#
# def review_step(update, context):
#     with Session() as session:
#         step_id = update.message.text
#         chat_data = context.chat_data
#         try:
#             step_id = int(step_id)
#             chat_data['step_id'] = step_id
#         except:
#             update.message.reply_text("Only number can be passed.")
#             return
#         chat_data = context.chat_data
#         gig_id = chat_data['gig_id']
#         gig = Gig.get_gig(session=session, id=gig_id)
#         global_step_to_submit = gig.steps.all()[step_id - 1].id
#         chat_data['global_id'] = global_step_to_submit
#         update.message.reply_text("Write review.")
#         return REVIEW
#
#
# def cancelprocess(update, context):
#     chat_data = context.chat_data
#     chat_data.clear()
#     update.message.reply_text("Cancelled process!")
#     return ConversationHandler.END
#
#
# def editsubwithgigid(update, context):
#     with Session() as session:
#         chat_data = context.chat_data
#         user = get_current_user(session=Session, update=update)
#         chat_data['user'] = user
#         if not user:
#             return
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                       '<i>e.g. /editsubwithgigid 1 or /editsubwithgigid 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         chat_data['gig'] = gig
#         chat_data['gig_id'] = recv_id
#         if not gig:
#             update.message.reply_text(f"Gig with id - {recv_id} does not exist")
#             return
#         giguser = GigUser.get_giguser_by_gigid_userid(session=session, gigid=recv_id, userid=user.id)
#         chat_data['giguser'] = giguser
#         if not giguser:
#             update.message.reply_text(f"You haven't taken gig #{recv_id}. You can take gig using command '/takegig {recv_id}'.")
#             return
#         update.message.reply_text("Enter step id which you want to edit.")
#         for _id, item in enumerate(giguser.stepgigusers.filter(StepGigUser.giguser_id == giguser.id).all()):
#             append_file_ids = []
#             if item.work_photo:
#                 photos = item.work_photo.split(',,,')
#                 for photo in photos:
#                     if photo.find('userworks/') != -1:
#                         file_id = photo.split('userworks/')[-1].split('.')[0]
#                         append_file_ids.append(file_id)
#             nl = '\n'
#             update.message.reply_text(f"<b>Step Id:</b> {_id + 1}\n\n"
#                                       f"<b>Submitted at:</b> {item.submitted_at.strftime('%d %b %Y, %I:%M %p') if item.submitted_at else ''}\n\n"
#                                       f"{'<b>Work Comment:</b>' + item.work_comment + nl * 2 if item.work_comment else ''}"
#                                       f"{'<b>Work Link:</b>' + item.work_link.replace(',,,', nl) + nl * 2 if item.work_link else ''}"
#                                       f"{'' if not append_file_ids else '<b>Work Photo: </b>'}", parse_mode='HTML', disable_web_page_preview=True)
#             for file in append_file_ids:
#                 update.message.reply_photo(file)
#         return STEP_ENTERED
#
#
# def step_entered(update, context):
#     with Session() as session:
#         step_id = update.message.text
#         chat_data = context.chat_data
#         try:
#             step_id = int(step_id)
#             chat_data['step_id'] = step_id
#         except:
#             update.message.reply_text("Only number can be passed.")
#             return
#         gig_id = chat_data['gig_id']
#         gig = Gig.get_gig(session=session, id=gig_id)
#         global_step_to_submit = gig.steps.all()[step_id - 1].id
#         chat_data['global_id'] = global_step_to_submit
#         keyboard = [
#             [
#                 InlineKeyboardButton("Edit Comment", callback_data='editcomment'),
#                 InlineKeyboardButton("Edit Links", callback_data='editlinks'),
#                 InlineKeyboardButton("Edit Photos", callback_data='editphotos'),
#             ]
#         ]
#         reply_markup = InlineKeyboardMarkup(keyboard)
#         update.message.reply_text("Select operation using inline keyboard button.", reply_markup=reply_markup)
#         return STEP_OPERATION
#
#
# def change_record(update, context):
#     with Session() as session:
#         chat_data = context.chat_data
#         query = update.callback_query
#         query.answer()
#         if query.data == 'editcomment':
#             query.edit_message_text(text=f"Enter new comment (use /canceloperation to cancel)")
#             return SELECTED_COMMENT
#         elif query.data == 'editlinks':
#             query.edit_message_text(text="Enter work links one by one (use /canceloperation to cancel)")
#             return SELECTED_LINKS
#         elif query.data == 'editphotos':
#             query.edit_message_text(text=f"Enter new photos one by one (use /canceloperation to cancel)")
#             return SELECTED_PHOTOS
#         else:
#             query.edit_message_text(text=f"Something is wrong. Try again later.")
#             return ConversationHandler.END
#
#
# def entered_comment(update, context):
#     with Session() as session:
#         comment = update.message.text
#         chat_data = context.chat_data
#         giguser = chat_data['giguser']
#         global_id = chat_data['global_id']
#         stepgiguser = StepGigUser.get_stepgiguser_by_stepid_giguserid(session=session, stepid=global_id, giguserid=giguser.id)
#         if stepgiguser:
#             work_comment = stepgiguser.update_comment(session=session, comment=comment)
#             update.message.reply_text(f"New comment - {stepgiguser.work_comment}")
#         return ConversationHandler.END
#
#
# def entered_links(update, context):
#     link = update.message.text
#     chat_data = context.chat_data
#     if not chat_data.get('work_link'):
#         chat_data['work_link'] = list()
#     chat_data['work_link'].append(link)
#     return SELECTED_LINKS
#
#
# def complete_links(update, context):
#     with Session() as session:
#         chat_data = context.chat_data
#         if not chat_data.get('work_link'):
#             chat_data['work_links'] = None
#         else:
#             chat_data['work_links'] = ',,,'.join(chat_data['work_link'])
#         giguser = chat_data['giguser']
#         global_id = chat_data['global_id']
#         stepgiguser = StepGigUser.get_stepgiguser_by_stepid_giguserid(session=session, stepid=global_id, giguserid=giguser.id)
#         if stepgiguser:
#             links = stepgiguser.update_link(session=session, links=chat_data['work_links'])
#             update.message.reply_text(f'Updated work links - {links.work_link}')
#         return ConversationHandler.END
#
#
# def complete_photos(update, context):
#     with Session() as session:
#         chat_data = context.chat_data
#         if not chat_data.get('work_photo'):
#             chat_data['work_photos'] = None
#             logger.info(f"Inside /editsubwithgigid. /completephotos. No work photos so storing chat_data['work_photos'] to None")
#         else:
#             chat_data['work_photos'] = ',,,'.join(chat_data['work_photo'])
#         giguser = chat_data['giguser']
#         global_id = chat_data['global_id']
#         stepgiguser = StepGigUser.get_stepgiguser_by_stepid_giguserid(session=session, stepid=global_id, giguserid=giguser.id)
#         if stepgiguser:
#             photos = stepgiguser.update_photo(session=session, photos=chat_data['work_photos'])
#             update.message.reply_text(f'Updated work photos - {photos.work_photo}')
#         return ConversationHandler.END
#
#
# def only_photo_accepted(update, context):
#     update.message.reply_text("Only photos are accepted. Submit photo of your work for the respective step!")
#     return WORKPHOTO
#
#
# def entered_photos(update, context):
#     update.message.reply_text("Photo received. Processing")
#     our_file = update.effective_message.photo[-1]
#     if our_file:
#         try:
#             file_id = our_file.file_id
#             # file_unique_id = our_file.file_unique_id
#             actual_file = our_file.get_file()
#
#             filepath_to_download = actual_file['file_path']
#
#             ext = filepath_to_download.split('.')[-1]
#             filename_to_store = f"{file_id}.{ext}"
#
#             logger.info(f"Inside /submitgig. Got photo. Saving photo as- {filename_to_store}")
#             update.message.reply_chat_action(action=constants.CHATACTION_UPLOAD_PHOTO)
#
#             # status = save_file_in_s3(filepath_to_download=filepath_to_download, bucket=BUCKET_NAME,
#             # filename_to_store=filename_to_store)
#             status = save_file_locally(filepath_to_download=filepath_to_download, filename_to_store=filename_to_store)
#             if status:
#                 update.message.reply_text('Image uploaded successfully..')
#             else:
#                 update.message.reply_text("Image not uploaded. Plz try again")
#
#             chat_data = context.chat_data
#             if not chat_data.get('work_photo'):
#                 chat_data['work_photo'] = list()
#             final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
#             chat_data['work_photo'].append(final_file_path)
#             logger.info(f"Inside /submitgig. Got photo. Final work photos - {chat_data['work_photo']}")
#         except:
#             logger.error(f"Update {update} caused error WHILE SAVING PHOTO- {context.error}")
#             logger.error(f"Exception while saving photo", exc_info=True)
#     update.message.reply_text('Photo processed, successfully!')
#     return SELECTED_PHOTOS
#
#
# def canceloperation(update, context):
#     update.message.reply_text("Editing Cancelled!")
#     chat_data = context.chat_data
#     chat_data.clear()
#     return ConversationHandler.END
#
#
# if __name__ == '__main__':
#     User.__table__.create(engine, checkfirst=True)
#     Gig.__table__.create(engine, checkfirst=True)
#     Step.__table__.create(engine, checkfirst=True)
#     GigUser.__table__.create(engine, checkfirst=True)
#     StepGigUser.__table__.create(engine, checkfirst=True)
#     print_all_tables()
#
#     updater = Updater(token='2098863676:AAFJHIw5MkNnWePBzSQAMFTYrKWCCXsgplg', use_context=True)
#     # set_bot_commands(updater)
#     dp: Dispatcher = updater.dispatcher
#
#     select_option_handler = ConversationHandler(
#         entry_points=[CallbackQueryHandler(edit_option, pattern='^editdescription|editsteps|editinstructions$')],
#         states={
#             SELECTED_DESCRIPTION: [MessageHandler(Filters.text and ~Filters.command, selected_description)],
#             SELECTED_STEPS: [MessageHandler(Filters.text and ~Filters.command, selected_steps)],
#             STEP_EDITION: [MessageHandler(Filters.text and ~Filters.command, step_edition)],
#             SELECTED_INSTRUCTIONS: [MessageHandler(Filters.text and ~Filters.command, selected_instructions)]
#         },
#         fallbacks=[CommandHandler('canceledit', canceledit)],
#     )
#
#     editgig_handler = ConversationHandler(
#         entry_points=[CommandHandler('editgig', editgig)],
#         states={
#             SELECTED_OPTION: [select_option_handler]
#         },
#         fallbacks=[CommandHandler('canceledit', canceledit)],
#     )
#
#     checksubwithgigid_handle = ConversationHandler(
#         entry_points=[CommandHandler('checksubwithgigid', checksubwithgigid)],
#         states={
#             SELECTED_USER: [MessageHandler(Filters.text and ~Filters.command, selected_user)],
#             STEP_REVIEW: [MessageHandler(Filters.text and ~Filters.command, review_step)],
#             REVIEW: [MessageHandler(Filters.text and ~Filters.command, review)]
#         },
#         fallbacks=[CommandHandler('cancelprocess', cancelprocess)],
#     )
#
#     gig_create_handler = ConversationHandler(
#         entry_points=[CommandHandler('addnewgig', addnewgig)],
#         states={
#         DESC: [MessageHandler(Filters.text and ~Filters.command, desc_of_new_gig)],
#         STEPS: [MessageHandler(Filters.text and ~Filters.command, steps_of_new_gig),
#                 CommandHandler('stepdone', done_with_steps)],
#         INSTRUCTIONS: [MessageHandler(Filters.text and ~Filters.command, instructions_of_new_gig)],
#         ConversationHandler.TIMEOUT: [MessageHandler(Filters.text | Filters.command, timeout_addnewgig)]
#         },
#         fallbacks=[CommandHandler('newgigcancel', newgigcancel)],
#         conversation_timeout=addnewgig_timeout_time
#     )
#
#     submit_gig_handler = ConversationHandler(
#         entry_points=[CommandHandler('submitgig', submitgig)],
#         states={
#             WORKCOMMENT: [CommandHandler('skipcomment', skipcomment),
#                           MessageHandler(Filters.text and ~Filters.command, submit_work_comment)],
#             WORKLINK: [CommandHandler('donelinks', donelinks),
#                        MessageHandler(Filters.text and ~Filters.command, submit_work_link)],
#             WORKPHOTO: [CommandHandler('donephotos', donephotos),
#                         MessageHandler(Filters.photo, submit_work_photo),
#                         MessageHandler(Filters.text, no_text_allowed),
#                         ],
#             ConversationHandler.TIMEOUT: [MessageHandler(Filters.text | Filters.command, timeout_submitgig)]
#         },
#         fallbacks=[CommandHandler('cancelsubmission', cancelsubmission)],
#         conversation_timeout=submitgig_timeout_time
#     )
#
#     edit_record_handler = ConversationHandler(
#         entry_points=[CallbackQueryHandler(change_record, pattern='^editcomment|editlinks|editphotos$')],
#         states={
#             SELECTED_COMMENT: [MessageHandler(Filters.text and ~Filters.command, entered_comment)],
#             SELECTED_LINKS: [CommandHandler('completelinks', complete_links),
#                             MessageHandler(Filters.text and ~Filters.command, entered_links)],
#             SELECTED_PHOTOS: [CommandHandler('completephotos', complete_photos),
#                               MessageHandler(Filters.photo, entered_photos),
#                               MessageHandler(Filters.text, only_photo_accepted)]
#         },
#         fallbacks=[CommandHandler('canceloperation', canceloperation)],
#     )
#
#     editsubwithgigid_handler = ConversationHandler(
#         entry_points=[CommandHandler('editsubwithgigid', editsubwithgigid)],
#         states={
#             STEP_ENTERED: [MessageHandler(Filters.text and ~Filters.command, step_entered)],
#             STEP_OPERATION: [edit_record_handler]
#         },
#         fallbacks=[CommandHandler('canceledit', canceledit)],
#     )
#
#     dp.add_handler(CommandHandler('start', start))
#     dp.add_handler(CommandHandler('help', help))
#     dp.add_handler(CommandHandler('gigs', gigs))
#     dp.add_handler(CommandHandler('giginfo', giginfo))
#     dp.add_handler(CommandHandler('mygigs', mygigs))
#     dp.add_handler(CommandHandler('takegig', takegig))
#     dp.add_handler(CommandHandler('mygigwithans', mygigwithans))
#     dp.add_handler(submit_gig_handler)
#
#     # Admin usable conversation handler
#     dp.add_handler(editgig_handler)
#     dp.add_handler(checksubwithgigid_handle)
#     dp.add_handler(CommandHandler('checksubwithgiguserid', checksubwithgiguserid))
#     dp.add_handler(editsubwithgigid_handler)
#     dp.add_handler(gig_create_handler)
#
#     dp.add_error_handler(error)
#     dp.add_handler(MessageHandler(Filters.text, anyrandom))
#     updater.start_polling()
#     updater.idle()


# /////////////////////////////////////////////////////////////////////////

# from telegram import constants
# from telegram.ext import Updater, Dispatcher, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackContext
# from models import User, Gig, Step, GigUser, StepGigUser
# from dbhelper import Session, engine
# from datetime import datetime
# import logging
# import boto3
# import os
# from dotenv import load_dotenv
# import requests
# from botocore.exceptions import NoCredentialsError
# from telegram.bot import BotCommand
# from bot_commands import suggested_commands
#
# load_dotenv()
#
# log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# logging.basicConfig(format=log_format, level=logging.INFO)
# logger = logging.getLogger(__name__)
#
# TOKEN = os.getenv('CTOGIGS_TELEGRAM_TOKEN')
# show_all_gigs_limit = 5
# DESC, STEPS, INSTRUCTIONS = range(3)
# WORKCOMMENT, WORKLINK, WORKPHOTO = range(3)
# ADMIN_CHAT_IDS = [1031241092]
#
# submitgig_timeout_time = 120
# addnewgig_timeout_time = 120
#
# FOLDERNAME_USERWORKS = 'userworks/'
# if not os.path.isdir(FOLDERNAME_USERWORKS):
#     os.mkdir(FOLDERNAME_USERWORKS)
#
# BUCKET_NAME = 'work-photos-ctogigsbot'
#
#
# def save_file_in_s3(filepath_to_download, bucket, filename_to_store):
#     s3 = boto3.client('s3', region_name='us-east-1')
#     # print(type(s3))
#     try:
#         logger.info(f"Inside /addlog. Saving image on S3")
#         imageResponse = requests.get(filepath_to_download, stream=True).raw
#         final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
#         s3.upload_fileobj(imageResponse, bucket, final_file_path)
#         logger.info("Image Saved on S3..")
#         return True
#     except FileNotFoundError:
#         logger.error('File not found..')
#         return False
#     except NoCredentialsError:
#         logger.info('Credentials not available')
#         return False
#     except:
#         logger.info('Some other error saving the file to S3')
#
#
# def start(update, context):
#     logging.info('Inside start')
#     first_name = update.message.from_user.first_name
#     last_name = update.message.from_user.last_name
#     chat_id = update.message.chat_id
#     tg_username = None
#     if update.message.from_user.username:
#         tg_username = update.message.from_user.username
#     created_at = datetime.now()
#     with Session() as session:
#         user = User.get_user_by_chatid(session=session, chat_id=chat_id)
#         if not user:
#             user = User(chat_id=chat_id, first_name=first_name, last_name=last_name, tg_username=tg_username,
#                         created_at=created_at)
#             session.add(user)
#             try:
#                 session.commit()
#                 update.message.reply_text(f"Welcome to CTOlogs, {user.first_name.title()}")
#             except:
#                 session.rollback()
#         else:
#                 update.message.reply_text(f"Welcome back, {user.first_name.title()}")
#
#
# def help(update, context):
#     update.message.reply_text('This bot allows you to explore and register for <b><i>python/fullstack/ml-dl-nlp/blockchain</i></b> related gigs. '
#                               '\n\nUse / to see list of all supported/usable commands!', parse_mode='HTML')
#
#
# def gigs(update, context):
#     with Session() as session:
#         user = get_current_user(session=session, update=update)
#         if not user:
#             return
#         all_gigs = session.query(Gig).order_by(Gig.created_at.desc()).limit(show_all_gigs_limit).all()
#         update.message.reply_text(f'Showing latest {show_all_gigs_limit} gigs\n'
#                                   f"Use <i>/giginfo 3</i> to check gig with 3", parse_mode='HTML')
#         for gig in all_gigs:
#             nl = '\n\n'
#             final_steps = nl.join([f"{_id+1}. {step.step_text}" for _id, step in enumerate(gig.steps.all())])
#             update.message.reply_text(f"<b>Gig Id:</b> {gig.id}\n\n"
#                                       f"<b>Desc:</b> {gig.short_description}\n\n"
#                                       f"<b>Steps:</b> \n{final_steps}\n\n"
#                                       f"<b>Instructions:</b> {gig.instructions}", parse_mode='HTML')
#
#
# def takegig(update, context):
#     with Session() as session:
#         current_user = get_current_user(update=update, session=session)
#         if not current_user:
#             return
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                      '<i>e.g. /takegig 1 or /takegig 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#
#         current_gig = Gig.get_gig(session=session, id=recv_id)
#         if not current_gig:
#             update.message.reply_text('Such a gig does not exist!')
#             return
#         current_user.gigusers.append(GigUser(gig_id=recv_id))
#         session.add(current_user)
#         try:
#             session.commit()
#         except:
#             session.rollback()
#             update.message.reply_text('Something went wrong. Please try again!')
#             return
#         else:
#             update.message.reply_text(f'You have signed up for Gig {recv_id}.\n'
#                                       f' Check /mygigs for details.')
#
#
# def giginfo(update, context):
#     with Session() as session:
#         user = get_current_user(session=session, update=update)
#         if not user:
#             return
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                       '<i>e.g. /giginfo 1 or /giginfo 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text(f"Gig with id - {recv_id} does not exist")
#         else:
#             nl = '\n\n'
#             final_steps = nl.join([f"{_id + 1}. {step.step_text}" for _id, step in enumerate(gig.steps.all())])
#             update.message.reply_text(f"<b>Gig Id:</b> {gig.id}\n\n"
#                                       f"<b>Desc:</b> {gig.short_description}\n\n"
#                                       f"<b>Steps:</b> \n{final_steps}\n\n"
#                                       f"<b>Instructions:</b> {gig.instructions}", parse_mode='HTML')
#
#
# def mygigs(update, context):
#     with Session() as session:
#         current_user = get_current_user(session=session, update=update)
#         if not current_user:
#             return
#         nl = '\n\n'
#         if not current_user.gigs:
#             update.message.reply_text("You haven't taken up any gigs yet!")
#             return
#         update.message.reply_text('You have registered for the following gigs')
#         for gig in current_user.gigs:
#             update.message.reply_text(f"Gig Id: {gig.id}\n\n"
#                                       f"Desc: {gig.short_description}\n\n"
#                                       f"Steps:\n{nl.join([step.step_text for step in gig.steps.all()])}")
#
#
# def addnewgig(update, context):
#     chat_id = update.message.chat_id
#     if chat_id not in ADMIN_CHAT_IDS:
#         update.message.reply_text('You do not have access to do this command')
#         return
#     update.message.reply_text("Alright, let's add a new gig. Write description in short.\n"
#                               "Use /newgigcancel to cancel.")
#     return DESC
#
#
# def desc_of_new_gig(update, context: CallbackContext):
#     description = update.message.text
#     chat_data = context.chat_data
#     chat_data['desc'] = description
#     update.message.reply_text("Got the description. Write steps one by one.\n"
#                               "Use /stepdone when done.")
#     return STEPS
#
#
# def steps_of_new_gig(update, context):
#     steps = update.message.text
#     chat_data = context.chat_data
#     if not chat_data.get('steps'):
#         chat_data['steps'] = list()
#     chat_data['steps'].append(steps)
#     return STEPS
#
#
# def done_with_steps(update, context):
#     update.message.reply_text("Noted the steps. Any instructions?")
#     return INSTRUCTIONS
#
#
# def instructions_of_new_gig(update, context):
#     instructions = update.message.text
#     update.message.reply_text("That's it!")
#     chat_data = context.chat_data
#     chat_data['instructions'] = instructions
#     save_new_gig(update, context)
#     return ConversationHandler.END
#
#
# def save_new_gig(update, context):
#     chat_id = update.message.chat_id
#     chat_data = context.chat_data
#     short_description = chat_data['desc']
#     instructions = chat_data['instructions']
#     steps = chat_data['steps']
#     owner_chat_id = chat_id
#     gig = Gig(short_description=short_description, instructions=instructions, owner_chat_id=owner_chat_id, created_at=datetime.now(), updated_at=datetime.now())
#     with Session() as session:
#         session.add(gig)
#         try:
#             session.commit()
#             update.message.reply_text(f'Gig created, {gig}')
#         except:
#             session.rollback()
#         for localstepid,step in enumerate(steps):
#             step_obj = Step(localstepid=localstepid + 1, gig_id=gig.id, step_text=step)
#             session.add(step_obj)
#         try:
#             session.commit()
#             chat_data.clear()
#             logger.info('chat_data cleared')
#         except:
#             session.rollback()
#
#
# def newgigcancel(update, context):
#     update.message.reply_text("Cancelled adding new gig")
#     chat_data = context.chat_data
#     chat_data.clear()
#     return ConversationHandler.END
#
#
# def anyrandom(update, context):
#     update.message.reply_text("Sorry, I am new to understand this!")
#
#
# def error(update, context: CallbackContext):
#     logger.warning(f'Update {update} caused an error {context.error}')
#
#
# def print_all_tables():
#     with Session() as session:
#         print([user for user in session.query(User).all()])
#         print([gig for gig in session.query(Gig).all()])
#         print([step for step in session.query(Step).all()])
#         print([giguser for giguser in session.query(GigUser).all()])
#         print([stepgiguser for stepgiguser in session.query(StepGigUser).all()])
#         # last_step = session.query(Step).all()[-1]
#         # print(last_step)
#         # print(last_step.gig)
#         # print(last_step.gig.short_description)
#         # user1 = session.query(User).all()[0]
#         # user1.gigusers.append(GigUser(gig_id=gig2.id))
#         # print(user1.gigs)
#         # gig2 = session.query(Gig).all()[1]
#         # global_step_to_submit = gig2.steps.all()[0].id
#         # print(gig2.steps.all())
#         # print(gig2.short_description)
#         # print(gig2.users)
#         # gu = GigUser(gig_id=gig2.id, taken_at=datetime.utcnow())
#         # gu = session.query(GigUser).all()[0]
#         # user1.gigusers.remove(gu)
#         # session.add(user1)
#         # try:
#         #     session.commit()
#         # except:
#         #     session.rollback()
#
#
# def get_current_user(session, update):
#     chat_id = update.message.chat_id
#     user = User.get_user_by_chatid(session=session, chat_id=chat_id)
#     if user:
#         return user
#     else:
#         update.message.reply_text('Use /start first then use this command again!')
#         return None
#
#
# def save_file_locally(filepath_to_download, filename_to_store):
#     response = requests.get(filepath_to_download)
#     final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
#     try:
#         logger.info(f"Inside /addlog. Saving image locally")
#         with open(final_file_path, 'wb') as f:
#             f.write(response.content)
#         logger.info("Image Saved locally..")
#         return True
#     except:
#         logger.info("Image could not be saved locally..")
#         return False
#
#
# def submitgig(update, context):
#     with Session() as session:
#         user = get_current_user(session=session, update=update)
#         if not user:
#             return
#         if not context.args:
#             update.message.reply_text("You need to pass gig_id next to the command.")
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number is allowed next to the command.')
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text("This is not a valid gig!")
#             return
#         giguser = GigUser.get_giguser_by_gigid_userid(session=session, userid=user.id, gigid=gig.id)
#         if not giguser:
#             update.message.reply_text(f"You need to TAKE this gig first. Use '/takegig {gig.id}' to register for that gig!")
#             return
#         # update.message.reply_text(f"Alright, accepting your work for Gig #{recv_id} \n(Use /cancelsubmission to cancel.)")
#         steps_submitted = giguser.stepgigusers.all()
#         global_step_to_submit = gig.steps.all()[0].id
#         local_step_to_submit = gig.steps.filter(Step.id == global_step_to_submit).first().localstepid
#
#         if not steps_submitted and local_step_to_submit == 1:
#             update.message.reply_text(
#                 f'Accepting your work for <b>Step {local_step_to_submit} (global step id {global_step_to_submit})</b> of <b>Gig {recv_id}</b>\n'
#                 f'(Use /cancelsubmission to cancel submission of step.)\n\n'
#                 f'This is FIRST STEP for which you are submitting your work!\n'
#                 f'Write comment if any, /skipcomment to skip.\n', parse_mode='HTML')
#         else:
#             steps_submitted_list = [stepgiguser.step_id for stepgiguser in steps_submitted]
#             last_step_submitted = max(steps_submitted_list)
#             last_step_of_gig = gig.steps.all()[-1].id
#             if last_step_submitted == last_step_of_gig:
#                 update.message.reply_text("You have submitted all the steps! No more steps left. Your gig submission is complete!")
#                 return
#             elif last_step_submitted < last_step_of_gig:
#                 global_step_to_submit = max(steps_submitted_list) + 1
#             update.message.reply_text(f"You have already submitted your work for step #{local_step_to_submit} (global step id #{global_step_to_submit - 1})!\n"
#                                       f"(Use /cancelsubmission to cancel.)\n\n"
#                                       f"Submit your work for {local_step_to_submit + 1} (global step id {global_step_to_submit}) step now.\n"
#                                       f"Write comment if any, /skipcomment to skip.")
#
#         chat_data = context.chat_data
#         chat_data['giguser_id'] = giguser.id
#         chat_data['global_step_to_submit'] = global_step_to_submit
#         # local_step_to_submit = Gig.get_gig(session=session, id=global_step_to_submit).localstepid
#     return WORKCOMMENT
#
#
# def submit_work_comment(update, context):
#     chat_data = context.chat_data
#     work_comment = update.message.text
#     chat_data['work_comment'] = work_comment
#     update.message.reply_text("Got your comment.\n"
#                               "Share github/drive/youtube link that points to your code or video demonstration of the step/code.\n"
#                               "Use /donelinks once done")
#     return WORKLINK
#
#
# def submit_work_link(update, context):
#     link = update.message.text
#     chat_data = context.chat_data
#     if not chat_data.get('work_link_temp'):
#         chat_data['work_link_temp'] = list()
#     chat_data['work_link_temp'].append(link)
#     return WORKLINK
#
#
# def submit_work_photo(update, context):
#     update.message.reply_text("Photo received. Processing")
#     our_file = update.effective_message.photo[-1]
#     if our_file:
#         try:
#             file_id = our_file.file_id
#             # file_unique_id = our_file.file_unique_id
#             actual_file = our_file.get_file()
#
#             filepath_to_download = actual_file['file_path']
#
#             ext = filepath_to_download.split('.')[-1]
#             filename_to_store = f"{file_id}.{ext}"
#
#             logger.info(f"Inside /submitgig. Got photo. Saving photo as- {filename_to_store}")
#             update.message.reply_chat_action(action=constants.CHATACTION_UPLOAD_PHOTO)
#
#             # status = save_file_in_s3(filepath_to_download=filepath_to_download, bucket=BUCKET_NAME,
#                                      # filename_to_store=filename_to_store)
#             status = save_file_locally(filepath_to_download=filepath_to_download, filename_to_store=filename_to_store)
#             if status:
#                 update.message.reply_text('Image uploaded successfully..')
#             else:
#                 update.message.reply_text("Image not uploaded. Plz try again")
#
#             chat_data = context.chat_data
#             if not chat_data.get('work_photo_temp'):
#                 chat_data['work_photo_temp'] = list()
#             final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
#             chat_data['work_photo_temp'].append(final_file_path)
#             logger.info(f"Inside /submitgig. Got photo. Final work photos - {chat_data['work_photo_temp']}")
#         except:
#             logger.error(f"Update {update} caused error WHILE SAVING PHOTO- {context.error}")
#             logger.error(f"Exception while saving photo", exc_info=True)
#     update.message.reply_text('Photo processed, successfully!')
#     return WORKPHOTO
#
#
# def skipcomment(update, context):
#     update.message.reply_text('Skipping comment.')
#     chat_data = context.chat_data
#     chat_data['work_comment'] = None
#     update.message.reply_text("Share github/drive/youtube link that points to your code or video demonstration of the step/code.\n"
#                               "Use /donelinks once done")
#     return WORKLINK
#
#
# def no_text_allowed(update, context):
#     update.message.reply_text("Only photos are accepted. Submit photo of your work for the respective step!")
#     return WORKPHOTO
#
#
# def donelinks(update, context):
#     chat_data = context.chat_data
#     if not chat_data.get('work_link_temp'):
#         chat_data['work_links'] = None
#     else:
#         chat_data['work_links'] = ',,,'.join(chat_data['work_link_temp'])
#     update.message.reply_text('Next, upload photos of code/output if any.\n'
#                         'Use /donephotos once done')
#     return WORKPHOTO
#
#
# def donephotos(update, context):
#     chat_data = context.chat_data
#     if not chat_data.get('work_photo_temp'):
#         chat_data['work_photos'] = None
#         logger.info(f"Inside /submitgig. /donephotos. No work photos so storing chat_data['work_photos'] to None")
#     else:
#         chat_data['work_photos'] = ',,,'.join(chat_data['work_photo_temp'])  # deliberately using this instead of comma, bcz if user somehow enters , in his work links, then it'll be split unnecessarily. so we want some unique identifier.
#
#     status = save_gig_submission(update, context)
#     if status:
#         update.message.reply_text('Submitted the gig successfully.\n'
#                         'Check /mygigwithans for more details.')
#     else:
#         update.message.reply_text("Something went wrong. Please submit the work for this step again.")
#     return ConversationHandler.END
#
#
# def cancelsubmission(update, context):
#     update.message.reply_text('Gig submission cancelled.')
#     return ConversationHandler.END
#
#
# def save_gig_submission(update, context):
#     chat_data = context.chat_data
#     giguser_id = chat_data['giguser_id']
#     step_id = chat_data['global_step_to_submit']
#     work_comment = chat_data['work_comment']
#     work_links = chat_data['work_links']
#     work_photos = chat_data['work_photos']
#     update.message.reply_text('Alright. Saving your record')
#
#     stepgiguser = StepGigUser(step_id=step_id, giguser_id=giguser_id, work_comment=work_comment, work_photo=work_photos, work_link=work_links, submitted_at=datetime.now())
#     with Session() as session:
#         session.add(stepgiguser)
#         try:
#             session.commit()
#             update.message.reply_text(f'StepGigUser created, {stepgiguser}')
#             chat_data.clear()
#             logger.info('chat_data cleared')
#         except:
#             update.message.reply_text("Something went wrong")
#             session.rollback()
#     return True
#
#
# def mygigwithans(update, context):
#     with Session() as session:
#         user: User = get_current_user(session=session, update=update)
#         if not user:
#             return
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                       '<i>e.g. /mygigwithans 1 or /mygigwithans 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         gig: Gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text(f"Gig with id - {recv_id} does not exist")
#             return
#         else:
#             giguser = GigUser.get_giguser_by_gigid_userid(session=session, gigid=gig.id, userid=user.id)
#             if not giguser:
#                 update.message.reply_text(f"You haven't take gig #{recv_id}.\nUse /takegig {recv_id} to take gig.")
#                 return
#             for _id, item in enumerate(giguser.stepgigusers.all()):
#                 append_file_ids = []
#                 if item.work_photo:
#                     photos = item.work_photo.split(',,,')
#                     for photo in photos:
#                         if photo.find('userworks/') != -1:
#                             file_id = photo.split('userworks/')[-1].split('.')[0]
#                             append_file_ids.append(file_id)
#                 nl = '\n'
#                 update.message.reply_text(f"<b>Step Id:</b> {_id + 1}\n\n"
#                                           f"<b>Submitted at:</b> {item.submitted_at.strftime('%d %b %Y, %I:%M %p')}\n\n"
#                                           f"{'<b>Work Comment:</b>' + item.work_comment + nl*2 if item.work_comment else ''}"
#                                           f"{'<b>Work Link:</b>' + item.work_link.replace(',,,', nl) + nl*2 if item.work_link else ''}"
#                                           f"{'' if not append_file_ids else '<b>Work Photo: </b>'}", parse_mode='HTML', disable_web_page_preview=True)
#                 for file in append_file_ids:
#                     update.message.reply_photo(file)
#
#
# def set_bot_commands(updater):
#     commands = [BotCommand(key, val) for key, val in dict(suggested_commands).items()]
#     updater.bot.set_my_commands(commands)
#
#
# def timeout_submitgig(update, context):
#     with Session() as session:
#         update.message.reply_text(f'Timeout. Use /submitgig again to submit step of gig. (Timeout limit - {submitgig_timeout_time} sec)')
#         chat_data = context.chat_data
#         chat_data.clear()
#         logger.info(f"Timeout for /submitgig")
#         return ConversationHandler.END
#
#
# def timeout_addnewgig(update, context):
#     with Session() as session:
#         update.message.reply_text(f'Timeout. Use /addnewgig again to submit step of gig. (Timeout limit - {addnewgig_timeout_time} sec)')
#         chat_data = context.chat_data
#         chat_data.clear()
#         logger.info(f"Timeout for /addnewgig")
#         return ConversationHandler.END
#
#
# if __name__ == '__main__':
#     User.__table__.create(engine, checkfirst=True)
#     Gig.__table__.create(engine, checkfirst=True)
#     Step.__table__.create(engine, checkfirst=True)
#     GigUser.__table__.create(engine, checkfirst=True)
#     StepGigUser.__table__.create(engine, checkfirst=True)
#     print_all_tables()
#
#     updater = Updater(token=TOKEN, use_context=True)
#     set_bot_commands(updater)
#     dp: Dispatcher = updater.dispatcher
#     dp.add_handler(CommandHandler('start', start))
#     dp.add_handler(CommandHandler('help', help))
#     dp.add_handler(CommandHandler('gigs', gigs))
#     dp.add_handler(CommandHandler('giginfo', giginfo))
#     dp.add_handler(CommandHandler('mygigs', mygigs))
#     dp.add_handler(CommandHandler('takegig', takegig))
#     dp.add_handler(CommandHandler('mygigwithans', mygigwithans))
#     gig_create_handler = ConversationHandler(
#         entry_points=[CommandHandler('addnewgig', addnewgig)],
#         states={
#         DESC: [MessageHandler(Filters.text and ~Filters.command, desc_of_new_gig)],
#         STEPS: [MessageHandler(Filters.text and ~Filters.command, steps_of_new_gig),
#                 CommandHandler('stepdone', done_with_steps)],
#         INSTRUCTIONS: [MessageHandler(Filters.text and ~Filters.command, instructions_of_new_gig)],
#         ConversationHandler.TIMEOUT: [MessageHandler(Filters.text | Filters.command, timeout_addnewgig)]
#         },
#         fallbacks=[CommandHandler('newgigcancel', newgigcancel)],
#         conversation_timeout=addnewgig_timeout_time
#     )
#
#     submit_gig_handler = ConversationHandler(
#         entry_points=[CommandHandler('submitgig', submitgig)],
#         states={
#             WORKCOMMENT: [CommandHandler('skipcomment', skipcomment),
#                           MessageHandler(Filters.text and ~Filters.command, submit_work_comment)],
#             WORKLINK: [CommandHandler('donelinks', donelinks),
#                        MessageHandler(Filters.text and ~Filters.command, submit_work_link)],
#             WORKPHOTO: [CommandHandler('donephotos', donephotos),
#                         MessageHandler(Filters.photo, submit_work_photo),
#                         MessageHandler(Filters.text, no_text_allowed)],
#             ConversationHandler.TIMEOUT: [MessageHandler(Filters.text | Filters.command, timeout_submitgig)]
#         },
#         fallbacks=[CommandHandler('cancelsubmission', cancelsubmission)],
#         conversation_timeout=submitgig_timeout_time
#     )
#     dp.add_handler(gig_create_handler)
#     dp.add_handler(submit_gig_handler)
#     dp.add_error_handler(error)
#     dp.add_handler(MessageHandler(Filters.text, anyrandom))
#     updater.start_polling()
#     updater.idle()






# //////////////////////////////////////////////////////////////////////////////////////////////////////////

# from telegram import constants, InlineKeyboardButton, InlineKeyboardMarkup
# from telegram.ext import Updater, Dispatcher, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
# from models import User, Gig, Step, GigUser, StepGigUser
# from dbhelper import Session, engine
# from datetime import datetime
# import logging
# import boto3
# import os
# from dotenv import load_dotenv
# import requests
# from botocore.exceptions import NoCredentialsError
# from telegram.bot import BotCommand
# from bot_commands import suggested_commands
#
# load_dotenv()
#
# log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# logging.basicConfig(format=log_format, level=logging.INFO)
# logger = logging.getLogger(__name__)
#
# # TOKEN = os.getenv('CTOGIGS_TELEGRAM_TOKEN')
# TOKEN = '2098863676:AAFJHIw5MkNnWePBzSQAMFTYrKWCCXsgplg'
# # TOKEN = '2098863676:AAEiJQ0KExb_SwFQoRrpFIMkcu1Cz_Itb3U'
# show_all_gigs_limit = 5
# DESC, STEPS, INSTRUCTIONS = range(3)
# WORKCOMMENT, WORKLINK, WORKPHOTO = range(3)
# SELECTED_OPTION, SELECTED_DESCRIPTION, SELECTED_STEPS, STEP_EDITION, SELECTED_INSTRUCTIONS = range(5)
# SELECTED_USER, STEP_REVIEW, REVIEW = range(3)
# STEP_ENTERED, STEP_OPERATION, SELECTED_COMMENT, SELECTED_LINKS, SELECTED_PHOTOS = range(5)
# ADMIN_CHAT_IDS = [1031241092]
# # ADMIN_CHAT_IDS = [1066103338]     # Mine
# submitgig_timeout_time = 120
# addnewgig_timeout_time = 120
#
# FOLDERNAME_USERWORKS = 'userworks/'
# if not os.path.isdir(FOLDERNAME_USERWORKS):
#     os.mkdir(FOLDERNAME_USERWORKS)
#
# BUCKET_NAME = 'work-photos-ctogigsbot'
#
# END=ConversationHandler.END
#
# def save_file_in_s3(filepath_to_download, bucket, filename_to_store):
#     s3 = boto3.client('s3', region_name='us-east-1')
#     # print(type(s3))
#     try:
#         logger.info(f"Inside /addlog. Saving image on S3")
#         imageResponse = requests.get(filepath_to_download, stream=True).raw
#         final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
#         s3.upload_fileobj(imageResponse, bucket, final_file_path)
#         logger.info("Image Saved on S3..")
#         return True
#     except FileNotFoundError:
#         logger.error('File not found..')
#         return False
#     except NoCredentialsError:
#         logger.info('Credentials not available')
#         return False
#     except:
#         logger.info('Some other error saving the file to S3')
#
#
# def start(update, context):
#     logging.info('Inside start')
#     first_name = update.message.from_user.first_name
#     last_name = update.message.from_user.last_name
#     chat_id = update.message.chat_id
#     tg_username = None
#     if update.message.from_user.username:
#         tg_username = update.message.from_user.username
#     created_at = datetime.now()
#     with Session() as session:
#         user = User.get_user_by_chatid(session=session, chat_id=chat_id)
#         if not user:
#             user = User(chat_id=chat_id, first_name=first_name, last_name=last_name, tg_username=tg_username,
#                         created_at=created_at)
#             session.add(user)
#             try:
#                 session.commit()
#                 update.message.reply_text(f"Welcome to CTOlogs, {user.first_name.title()}")
#             except:
#                 session.rollback()
#         else:
#             update.message.reply_text(f"Welcome back, {user.first_name.title()}")
#
#
# def help(update, context):
#     update.message.reply_text('This bot allows you to explore and register for <b><i>python/fullstack/ml-dl-nlp/blockchain</i></b> related gigs. '
#                               '\n\nUse / to see list of all supported/usable commands!', parse_mode='HTML')
#
#
# def gigs(update, context):
#     with Session() as session:
#         user = get_current_user(session=session, update=update)
#         if not user:
#             return
#         all_gigs = session.query(Gig).order_by(Gig.created_at.desc()).limit(show_all_gigs_limit).all()
#         if not all_gigs:
#             update.message.reply_text("Gig not created yet!")
#             return
#         update.message.reply_text(f'Showing latest {show_all_gigs_limit} gigs\n'
#                                   f"Use <i>/giginfo 3</i> to check gig with 3", parse_mode='HTML')
#         for gig in all_gigs:
#             nl = '\n\n'
#             final_steps = nl.join([f"{_id+1}. {step.step_text}" for _id, step in enumerate(gig.steps.all())])
#             update.message.reply_text(f"<b>Gig Id:</b> {gig.id}\n\n"
#                                       f"<b>Desc:</b> {gig.short_description}\n\n"
#                                       f"<b>Steps:</b> \n{final_steps}\n\n"
#                                       f"<b>Instructions:</b> {gig.instructions}", parse_mode='HTML')
#
#
# def takegig(update, context):
#     with Session() as session:
#         current_user = get_current_user(update=update, session=session)
#         if not current_user:
#             return
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                      '<i>e.g. /takegig 1 or /takegig 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#
#         current_gig = Gig.get_gig(session=session, id=recv_id)
#         if not current_gig:
#             update.message.reply_text('Such a gig does not exist!')
#             return
#         current_user.gigusers.append(GigUser(gig_id=recv_id))
#         session.add(current_user)
#         try:
#             session.commit()
#         except:
#             session.rollback()
#             update.message.reply_text('Something went wrong. Please try again!')
#             return
#         else:
#             update.message.reply_text(f'You have signed up for Gig {recv_id}.\n'
#                                       f' Check /mygigs for details.')
#
#
# def giginfo(update, context):
#     with Session() as session:
#         user = get_current_user(session=session, update=update)
#         if not user:
#             return
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                       '<i>e.g. /giginfo 1 or /giginfo 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text(f"Gig with id - {recv_id} does not exist")
#         else:
#             nl = '\n\n'
#             final_steps = nl.join([f"{_id + 1}. {step.step_text}" for _id, step in enumerate(gig.steps.all())])
#             update.message.reply_text(f"<b>Gig Id:</b> {gig.id}\n\n"
#                                       f"<b>Desc:</b> {gig.short_description}\n\n"
#                                       f"<b>Steps:</b> \n{final_steps}\n\n"
#                                       f"<b>Instructions:</b> {gig.instructions}", parse_mode='HTML')
#
#
# def mygigs(update, context):
#     with Session() as session:
#         current_user = get_current_user(session=session, update=update)
#         if not current_user:
#             return
#         nl = '\n\n'
#         if not current_user.gigs:
#             update.message.reply_text("You haven't taken up any gigs yet!")
#             return
#         update.message.reply_text('You have registered for the following gigs')
#         for gig in current_user.gigs:
#             update.message.reply_text(f"Gig Id: {gig.id}\n\n"
#                                       f"Desc: {gig.short_description}\n\n"
#                                       f"Steps:\n{nl.join([step.step_text for step in gig.steps.all()])}")
#
#
# def addnewgig(update, context):
#     chat_id = update.message.chat_id
#     if chat_id not in ADMIN_CHAT_IDS:
#         update.message.reply_text('You do not have access to do this command')
#         return
#     update.message.reply_text("Alright, let's add a new gig. Write description in short.\n"
#                               "Use /newgigcancel to cancel.")
#     return DESC
#
#
# def desc_of_new_gig(update, context: CallbackContext):
#     description = update.message.text
#     chat_data = context.chat_data
#     chat_data['desc'] = description
#     update.message.reply_text("Got the description. Write steps one by one.\n"
#                               "Use /stepdone when done.")
#     return STEPS
#
#
# def steps_of_new_gig(update, context):
#     steps = update.message.text
#     chat_data = context.chat_data
#     if not chat_data.get('steps'):
#         chat_data['steps'] = list()
#     chat_data['steps'].append(steps)
#     return STEPS
#
#
# def done_with_steps(update, context):
#     update.message.reply_text("Noted the steps. Any instructions?")
#     return INSTRUCTIONS
#
#
# def instructions_of_new_gig(update, context):
#     instructions = update.message.text
#     update.message.reply_text("That's it!")
#     chat_data = context.chat_data
#     chat_data['instructions'] = instructions
#     save_new_gig(update, context)
#     return ConversationHandler.END
#
#
# def save_new_gig(update, context):
#     chat_id = update.message.chat_id
#     chat_data = context.chat_data
#     short_description = chat_data['desc']
#     instructions = chat_data['instructions']
#     steps = chat_data['steps']
#     owner_chat_id = chat_id
#     gig = Gig(short_description=short_description, instructions=instructions, owner_chat_id=owner_chat_id, created_at=datetime.now(), updated_at=datetime.now())
#     with Session() as session:
#         session.add(gig)
#         try:
#             session.commit()
#             update.message.reply_text(f'Gig created, {gig}')
#         except:
#             session.rollback()
#         for localstepid, step in enumerate(steps):
#             step_obj = Step(localstepid=localstepid + 1, gig_id=gig.id, step_text=step)
#             session.add(step_obj)
#         try:
#             session.commit()
#             chat_data.clear()
#             logger.info('chat_data cleared')
#         except:
#             session.rollback()
#
#
# def newgigcancel(update, context):
#     update.message.reply_text("Cancelled adding new gig")
#     chat_data = context.chat_data
#     chat_data.clear()
#     return ConversationHandler.END
#
#
# def anyrandom(update, context):
#     update.message.reply_text("Sorry, I am new to understand this!")
#
#
# def error(update, context: CallbackContext):
#     logger.warning(f'Update {update} caused an error {context.error}')
#
#
# def print_all_tables():
#     with Session() as session:
#         print([user for user in session.query(User).all()])
#         print([gig for gig in session.query(Gig).all()])
#         print([step for step in session.query(Step).all()])
#         print([giguser for giguser in session.query(GigUser).all()])
#         print([stepgiguser for stepgiguser in session.query(StepGigUser).all()])
#
#
# def get_current_user(session, update):
#     chat_id = update.message.chat_id
#     user = User.get_user_by_chatid(session=session, chat_id=chat_id)
#     if user:
#         return user
#     else:
#         update.message.reply_text('Use /start first then use this command again!')
#         return None
#
#
# def save_file_locally(filepath_to_download, filename_to_store):
#     response = requests.get(filepath_to_download)
#     final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
#     try:
#         logger.info(f"Inside /addlog. Saving image locally")
#         with open(final_file_path, 'wb') as f:
#             f.write(response.content)
#         logger.info("Image Saved locally..")
#         return True
#     except:
#         logger.info("Image could not be saved locally..")
#         return False
#
#
# def submitgig(update, context):
#     with Session() as session:
#         user = get_current_user(session=session, update=update)
#         if not user:
#             return
#         if not context.args:
#             update.message.reply_text("You need to pass gig_id next to the command.")
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number is allowed next to the command.')
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text("This is not a valid gig!")
#             return
#         giguser = GigUser.get_giguser_by_gigid_userid(session=session, userid=user.id, gigid=gig.id)
#         if not giguser:
#             update.message.reply_text(f"You need to TAKE this gig first. Use '/takegig {gig.id}' to register for that gig!")
#             return
#         # update.message.reply_text(f"Alright, accepting your work for Gig #{recv_id} \n(Use /cancelsubmission to cancel.)")
#         steps_submitted = giguser.stepgigusers.all()
#         global_step_to_submit = gig.steps.all()[0].id
#         local_step_to_submit = gig.steps.filter(Step.id == global_step_to_submit).first().localstepid
#
#         if not steps_submitted and local_step_to_submit == 1:
#             update.message.reply_text(
#                 f'Accepting your work for <b>Step {local_step_to_submit} (global step id {global_step_to_submit})</b> of <b>Gig {recv_id}</b>\n'
#                 f'(Use /cancelsubmission to cancel submission of step.)\n\n'
#                 f'This is FIRST STEP for which you are submitting your work!\n'
#                 f'Write comment if any, /skipcomment to skip.\n', parse_mode='HTML')
#         else:
#             steps_submitted_list = [stepgiguser.step_id for stepgiguser in steps_submitted]
#             last_step_submitted = max(steps_submitted_list)
#             last_step_of_gig = gig.steps.all()[-1].id
#             if last_step_submitted == last_step_of_gig:
#                 update.message.reply_text("You have submitted all the steps! No more steps left. Your gig submission is complete!")
#                 return
#             elif last_step_submitted < last_step_of_gig:
#                 global_step_to_submit = max(steps_submitted_list) + 1
#                 update.message.reply_text(f"You have already submitted your work for step #{local_step_to_submit} (global step id #{global_step_to_submit - 1})!\n"
#                                       f"(Use /cancelsubmission to cancel.)\n\n"
#                                       f"Submit your work for {local_step_to_submit + 1} (global step id {global_step_to_submit}) step now.\n"
#                                       f"Write comment if any, /skipcomment to skip.")
#
#         chat_data = context.chat_data
#         chat_data['giguser_id'] = giguser.id
#         chat_data['global_step_to_submit'] = global_step_to_submit
#         # local_step_to_submit = Gig.get_gig(session=session, id=global_step_to_submit).localstepid
#     return WORKCOMMENT
#
#
# def submit_work_comment(update, context):
#     chat_data = context.chat_data
#     work_comment = update.message.text
#     chat_data['work_comment'] = work_comment
#     update.message.reply_text("Got your comment.\n"
#                               "Share github/drive/youtube link that points to your code or video demonstration of the step/code.\n"
#                               "Use /donelinks once done")
#     return WORKLINK
#
#
# def submit_work_link(update, context):
#     link = update.message.text
#     chat_data = context.chat_data
#     if not chat_data.get('work_link_temp'):
#         chat_data['work_link_temp'] = list()
#     chat_data['work_link_temp'].append(link)
#     return WORKLINK
#
#
# def submit_work_photo(update, context):
#     update.message.reply_text("Photo received. Processing")
#     our_file = update.effective_message.photo[-1]
#     if our_file:
#         try:
#             file_id = our_file.file_id
#             # file_unique_id = our_file.file_unique_id
#             actual_file = our_file.get_file()
#
#             filepath_to_download = actual_file['file_path']
#
#             ext = filepath_to_download.split('.')[-1]
#             filename_to_store = f"{file_id}.{ext}"
#
#             logger.info(f"Inside /submitgig. Got photo. Saving photo as- {filename_to_store}")
#             update.message.reply_chat_action(action=constants.CHATACTION_UPLOAD_PHOTO)
#
#             # status = save_file_in_s3(filepath_to_download=filepath_to_download, bucket=BUCKET_NAME,
#             # filename_to_store=filename_to_store)
#             status = save_file_locally(filepath_to_download=filepath_to_download, filename_to_store=filename_to_store)
#             if status:
#                 update.message.reply_text('Image uploaded successfully..')
#             else:
#                 update.message.reply_text("Image not uploaded. Plz try again")
#
#             chat_data = context.chat_data
#             if not chat_data.get('work_photo_temp'):
#                 chat_data['work_photo_temp'] = list()
#             final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
#             chat_data['work_photo_temp'].append(final_file_path)
#             logger.info(f"Inside /submitgig. Got photo. Final work photos - {chat_data['work_photo_temp']}")
#         except:
#             logger.error(f"Update {update} caused error WHILE SAVING PHOTO- {context.error}")
#             logger.error(f"Exception while saving photo", exc_info=True)
#     update.message.reply_text('Photo processed, successfully!')
#     return WORKPHOTO
#
#
# def skipcomment(update, context):
#     update.message.reply_text('Skipping comment.')
#     chat_data = context.chat_data
#     chat_data['work_comment'] = None
#     update.message.reply_text("Share github/drive/youtube link that points to your code or video demonstration of the step/code.\n"
#                               "Use /donelinks once done")
#     return WORKLINK
#
#
# def no_text_allowed(update, context):
#     update.message.reply_text("Only photos are accepted. Submit photo of your work for the respective step!")
#     return WORKPHOTO
#
#
# def donelinks(update, context):
#     chat_data = context.chat_data
#     if not chat_data.get('work_link_temp'):
#         chat_data['work_links'] = None
#     else:
#         chat_data['work_links'] = ',,,'.join(chat_data['work_link_temp'])
#     update.message.reply_text('Next, upload photos of code/output if any.\n'
#                         'Use /donephotos once done')
#     return WORKPHOTO
#
#
# def donephotos(update, context):
#     chat_data = context.chat_data
#     if not chat_data.get('work_photo_temp'):
#         chat_data['work_photos'] = None
#         logger.info(f"Inside /submitgig. /donephotos. No work photos so storing chat_data['work_photos'] to None")
#     else:
#         chat_data['work_photos'] = ',,,'.join(chat_data['work_photo_temp'])  # deliberately using this instead of comma, bcz if user somehow enters , in his work links, then it'll be split unnecessarily. so we want some unique identifier.
#
#     status = save_gig_submission(update, context)
#     if status:
#         update.message.reply_text('Submitted the gig successfully.\n'
#                         'Check /mygigwithans for more details.')
#     else:
#         update.message.reply_text("Something went wrong. Please submit the work for this step again.")
#     return ConversationHandler.END
#
#
# def cancelsubmission(update, context):
#     update.message.reply_text('Gig submission cancelled.')
#     return ConversationHandler.END
#
#
# def save_gig_submission(update, context):
#     chat_data = context.chat_data
#     giguser_id = chat_data['giguser_id']
#     step_id = chat_data['global_step_to_submit']
#     work_comment = chat_data['work_comment']
#     work_links = chat_data['work_links']
#     work_photos = chat_data['work_photos']
#     update.message.reply_text('Alright. Saving your record')
#
#     stepgiguser = StepGigUser(step_id=step_id, giguser_id=giguser_id, work_comment=work_comment, work_photo=work_photos, work_link=work_links, submitted_at=datetime.now())
#     with Session() as session:
#         session.add(stepgiguser)
#         try:
#             session.commit()
#             update.message.reply_text(f'StepGigUser created, {stepgiguser}', disable_web_page_preview=True)
#             chat_data.clear()
#             logger.info('chat_data cleared')
#         except:
#             update.message.reply_text("Something went wrong")
#             session.rollback()
#     return True
#
#
# def mygigwithans(update, context):
#     with Session() as session:
#         user: User = get_current_user(session=session, update=update)
#         if not user:
#             return
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                       '<i>e.g. /mygigwithans 1 or /mygigwithans 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text(f"Gig with id - {recv_id} does not exist")
#             return
#         giguser = GigUser.get_giguser_by_gigid_userid(session=session, gigid=gig.id, userid=user.id)
#         if not giguser:
#             update.message.reply_text(f"You need to TAKE this gig first. Use '/takegig {gig.id}' to register for that gig!")
#             return
#         for _id, item in enumerate(giguser.stepgigusers.all()):
#             append_file_ids = []
#             if item.work_photo:
#                 photos = item.work_photo.split(',,,')
#                 for photo in photos:
#                     if photo.find('userworks/') != -1:
#                         file_id = photo.split('userworks/')[-1].split('.')[0]
#                         append_file_ids.append(file_id)
#             nl = '\n'
#             update.message.reply_text(f"<b>Step Id:</b> {_id + 1}\n\n"
#                                       f"<b>Submitted at:</b> {item.submitted_at.strftime('%d %b %Y, %I:%M %p') if item.submitted_at else ''}\n\n"
#                                       f"<b>Review:</b> {item.review}{nl * 2}"
#                                       f"<b>Reviewed at:</b> {item.reviewed_at.strftime('%d %b %Y, %I:%M %p')}{nl*2}"
#                                       f"{'<b>Work Comment:</b>' + item.work_comment + nl * 2 if item.work_comment else ''}"
#                                       f"{'<b>Work Link:</b>' + item.work_link.replace(',,,', nl) + nl * 2 if item.work_link else ''}"
#                                       f"{'' if not append_file_ids else '<b>Work Photo: </b>'}", parse_mode='HTML', disable_web_page_preview=True)
#             for file in append_file_ids:
#                 update.message.reply_photo(file)
#
#
# def set_bot_commands(updater):
#     commands = [BotCommand(key, val) for key, val in dict(suggested_commands).items()]
#     updater.bot.set_my_commands(commands)
#
#
# def timeout_submitgig(update, context):
#     with Session() as session:
#         update.message.reply_text(f'Timeout. Use /submitgig again to submit step of gig. (Timeout limit - {submitgig_timeout_time} sec)')
#         chat_data = context.chat_data
#         chat_data.clear()
#         logger.info(f"Timeout for /submitgig")
#         return ConversationHandler.END
#
#
# def timeout_addnewgig(update, context):
#     with Session() as session:
#         update.message.reply_text(f'Timeout. Use /addnewgig again to submit step of gig. (Timeout limit - {addnewgig_timeout_time} sec)')
#         chat_data = context.chat_data
#         chat_data.clear()
#         logger.info(f"Timeout for /addnewgig")
#         return ConversationHandler.END
#
#
# def editgig(update, context):
#     chat_data = context.chat_data
#     chat_id = update.message.chat_id
#     if chat_id not in ADMIN_CHAT_IDS:
#         update.message.reply_text('You do not have access to do this command')
#         return
#     with Session() as session:
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                       '<i>e.g. /editgig 1 or /editgig 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#             chat_data['recv_id'] = recv_id
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text(f"Gig with id - {recv_id} does not exist")
#             return
#         else:
#             keyboard = [
#                 [
#                     InlineKeyboardButton("Edit Description", callback_data='editdescription'),
#                     InlineKeyboardButton("Edit Steps", callback_data='editsteps'),
#                     InlineKeyboardButton("Edit Instructions", callback_data='editinstructions'),
#                 ]
#             ]
#             reply_markup = InlineKeyboardMarkup(keyboard)
#             update.message.reply_text(f"Gig #{recv_id} details are shown below:\n\n{gig}", reply_markup=reply_markup)
#             return SELECTED_OPTION
#
#
# def edit_option(update, context):
#     with Session() as session:
#         chat_data = context.chat_data
#         gig = Gig.get_gig(session=session, id=chat_data['recv_id'])
#         if not gig:
#             return
#         query = update.callback_query
#         query.answer()
#         if query.data == 'editdescription':
#             query.edit_message_text(text=f"Enter new description (/canceledit to cancel)")
#             return SELECTED_DESCRIPTION
#         elif query.data == 'editsteps':
#             chat_data = context.chat_data
#             recv_id = chat_data['recv_id']
#             nl = '\n\n'
#             query.edit_message_text(text=f"Enter step id which you want to edit.{nl}The steps of gig #{recv_id} are given below:\n{nl.join([f'{_id + 1}. {step.step_text}' for _id, step in enumerate(gig.steps.all())])}")
#             return SELECTED_STEPS
#         elif query.data == 'editinstructions':
#             query.edit_message_text(text=f"Enter new instructions (/canceledit to cancel)")
#             return SELECTED_INSTRUCTIONS
#         else:
#             query.edit_message_text(text=f"Something is wrong. Try again later.")
#             return ConversationHandler.END
#
#
# def checksubwithgigid(update, context):
#     chat_id = update.message.chat_id
#     if chat_id not in ADMIN_CHAT_IDS:
#         update.message.reply_text('You do not have access to do this command')
#         return
#     with Session() as session:
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                       '<i>e.g. /checksubwithgigid 1 or /checksubwithgigid 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#             chat_data = context.chat_data
#             chat_data['gig_id'] = recv_id
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         user = get_current_user(session=session, update=update)
#         if not user:
#             update.message.reply_text("First use /start command.")
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text(f"Gig with id - {recv_id} does not exist")
#             return
#         giguser = GigUser.get_giguser_by_gigid_userid(session=session, gigid=recv_id, userid=user.id)
#
#         if not giguser:
#             update.message.reply_text(f"You haven't take gig #{recv_id}. You can take gig using command '/takegig {recv_id}.'")
#             return
#         nl = '\n\n'
#         update.message.reply_text("Enter user id")
#         update.message.reply_text(f"List of users who taken gig #{recv_id} is given below:{nl}{nl.join([f'{item.id}. {item.first_name} {item.last_name}' for item in gig.users])}")
#         return SELECTED_USER
#
#
# def checksubwithgiguserid(update, context):
#     chat_id = update.message.chat_id
#     if chat_id not in ADMIN_CHAT_IDS:
#         update.message.reply_text('You do not have access to do this command')
#         return
#     with Session() as session:
#         if not context.args:
#             update.message.reply_text('You need to pass giguser id next to the command.\n'
#                                       '<i>e.g. /checksubwithgiguserid 1 or /checksubwithgiguserid 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         giguser = GigUser.get_giguser_by_id(session=session, id=recv_id)
#         if not giguser:
#             update.message.reply_text(f"Giguser id #{recv_id} not present!")
#             return
#         user = giguser.user
#         user_first_name = user.first_name
#         user_last_name = user.last_name
#         update.message.reply_text(f"Submission of gig #{giguser.gig_id} for user {user_first_name} {user_last_name}is given below:\n\n")
#         for _id, item in enumerate(giguser.stepgigusers.filter(StepGigUser.giguser_id == recv_id).all()):
#             append_file_ids = []
#             if item.work_photo:
#                 photos = item.work_photo.split(',,,')
#                 for photo in photos:
#                     if photo.find('userworks/') != -1:
#                         file_id = photo.split('userworks/')[-1].split('.')[0]
#                         append_file_ids.append(file_id)
#             nl = '\n'
#             update.message.reply_text(f"<b>Step Id:</b> {_id + 1}\n\n"
#                                       f"<b>Submitted at:</b> {item.submitted_at.strftime('%d %b %Y, %I:%M %p') if item.submitted_at else ''}\n\n"
#                                       f"{'<b>Work Comment:</b>' + item.work_comment + nl * 2 if item.work_comment else ''}"
#                                       f"{'<b>Work Link:</b>' + item.work_link.replace(',,,', nl) + nl * 2 if item.work_link else ''}"
#                                       f"{'' if not append_file_ids else '<b>Work Photo: </b>'}", parse_mode='HTML', disable_web_page_preview=True)
#             for file in append_file_ids:
#                 update.message.reply_photo(file)
#
#
# def selected_user(update, context):
#     with Session() as session:
#         user_id = update.message.text
#         try:
#             user_id = int(user_id)
#         except:
#             update.message.reply_text("Only numbers can be passed.")
#             return
#         user = User.get_user_by_id(session=session, id=user_id)
#         if not user:
#             update.message.reply_text(f"User id does not exist!")
#             return
#         chat_data = context.chat_data
#         chat_data['user_id'] = user_id
#         gig_id = chat_data['gig_id']
#         giguser = GigUser.get_giguser_by_gigid_userid(session=session, gigid=gig_id, userid=user_id)
#         chat_data['giguser_id'] = giguser.id
#         for _id, step in enumerate(giguser.stepgigusers.filter(StepGigUser.giguser_id == giguser.id).all()):
#             append_file_ids = []
#             if step.work_photo:
#                 photos = step.work_photo.split(',,,')
#                 for photo in photos:
#                     if photo.find('userworks/') != -1:
#                         file_id = photo.split('userworks/')[-1].split('.')[0]
#                         append_file_ids.append(file_id)
#             nl = '\n\n'
#             update.message.reply_text(f"<b>Step Id:</b> {_id +1 if step.step_id else ''}{nl}"
#                                       f"{'<b>Work Comment:</b> ' + step.work_comment if step.work_comment else ''}{nl}"
#                                       f"{'' if not step.work_photo else '<b>Work Photo:</b> '}", parse_mode='HTML', disable_web_page_preview=True)
#             for file in append_file_ids:
#                 update.message.reply_photo(file)
#         update.message.reply_text("Enter step id which you want to give review if any. (Use /cancelprocess to cancel)")
#         return STEP_REVIEW
#
#
# def selected_description(update, context):
#     with Session() as session:
#         description = update.message.text
#         chat_data = context.chat_data
#         gig = Gig.get_gig(session=session, id=chat_data['recv_id'])
#         if gig:
#             description = gig.update_description(session=session, description=description)
#             update.message.reply_text(f"New description - {description.short_description}")
#         return ConversationHandler.END
#
#
# def canceledit(update, context):
#     update.message.reply_text("Editing Cancelled!")
#     chat_data = context.chat_data
#     chat_data.clear()
#     return ConversationHandler.END
#
#
# def selected_steps(update, context):
#     step_id = update.message.text
#     try:
#         step_id = int(step_id)
#     except:
#         update.message.reply_text("Step id must be integer.")
#     chat_data = context.chat_data
#     chat_data['step_id'] = step_id
#     update.message.reply_text("Write step (use /canceledit to cancel)")
#     return STEP_EDITION
#
#
# def step_edition(update, context):
#     with Session() as session:
#         step_text = update.message.text
#         chat_data = context.chat_data
#         gig = Gig.get_gig(session=session, id=chat_data['recv_id'])
#         step_id = chat_data['step_id']
#         # nl.join([f'{_id + 1}. {step.step_text}' for _id, step in enumerate(gig.steps.all())])
#         step = gig.steps.filter(Step.localstepid == step_id).first()
#         if step:
#             step.update_step(session=session, step_text=step_text)
#             update.message.reply_text(f"Updated step - {step.step_text}")
#             return ConversationHandler.END
#         else:
#             update.message.reply_text("Step id not present!")
#             return ConversationHandler.END
#
#
# def selected_instructions(update, context):
#     with Session() as session:
#         chat_data = context.chat_data
#         instructions = update.message.text
#         gig = Gig.get_gig(session=session, id=chat_data['recv_id'])
#         if gig:
#             instruction = gig.update_instructions(session=session, instructions=instructions)
#             update.message.reply_text(f"New instructions - {instruction.instructions}")
#         return ConversationHandler.END
#
#
# def review(update, context):
#     with Session() as session:
#         chat_data = context.chat_data
#         giguser_id = chat_data['giguser_id']
#         global_id = chat_data['global_id']
#         print(global_id)
#         step_id = chat_data['step_id']
#         review = update.message.text
#         data = StepGigUser.get_stepgiguser_by_stepid_giguserid(session=session, stepid=global_id, giguserid=giguser_id)
#         if data:
#             updated_review = data.update_review(session=session, review=review)
#             update.message.reply_text(f"Updated review - {updated_review.review}\n\n")
#             return ConversationHandler.END
#         else:
#             update.message.reply_text("Something went wrong!")
#             return ConversationHandler.END
#
#
# def review_step(update, context):
#     with Session() as session:
#         step_id = update.message.text
#         chat_data = context.chat_data
#         try:
#             step_id = int(step_id)
#             chat_data['step_id'] = step_id
#         except:
#             update.message.reply_text("Only number can be passed.")
#             return
#         chat_data = context.chat_data
#         gig_id = chat_data['gig_id']
#         gig = Gig.get_gig(session=session, id=gig_id)
#         global_step_to_submit = gig.steps.all()[step_id - 1].id
#         chat_data['global_id'] = global_step_to_submit
#         update.message.reply_text("Write review.")
#         return REVIEW
#
#
# def cancelprocess(update, context):
#     chat_data = context.chat_data
#     chat_data.clear()
#     update.message.reply_text("Cancelled process!")
#     return ConversationHandler.END
#
#
# def editsubwithgigid(update, context):
#     with Session() as session:
#         chat_data = context.chat_data
#         user = get_current_user(session=Session, update=update)
#         chat_data['user'] = user
#         if not user:
#             return
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                       '<i>e.g. /editsubwithgigid 1 or /editsubwithgigid 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         chat_data['gig'] = gig
#         chat_data['gig_id'] = recv_id
#         if not gig:
#             update.message.reply_text(f"Gig with id - {recv_id} does not exist")
#             return
#         giguser = GigUser.get_giguser_by_gigid_userid(session=session, gigid=recv_id, userid=user.id)
#         chat_data['giguser'] = giguser
#         if not giguser:
#             update.message.reply_text(f"You haven't taken gig #{recv_id}. You can take gig using command '/takegig {recv_id}'.")
#             return
#         update.message.reply_text("Enter step id which you want to edit.")
#         for _id, item in enumerate(giguser.stepgigusers.filter(StepGigUser.giguser_id == giguser.id).all()):
#             append_file_ids = []
#             if item.work_photo:
#                 photos = item.work_photo.split(',,,')
#                 for photo in photos:
#                     if photo.find('userworks/') != -1:
#                         file_id = photo.split('userworks/')[-1].split('.')[0]
#                         append_file_ids.append(file_id)
#             nl = '\n'
#             update.message.reply_text(f"<b>Step Id:</b> {_id + 1}\n\n"
#                                       f"<b>Submitted at:</b> {item.submitted_at.strftime('%d %b %Y, %I:%M %p') if item.submitted_at else ''}\n\n"
#                                       f"{'<b>Work Comment:</b>' + item.work_comment + nl * 2 if item.work_comment else ''}"
#                                       f"{'<b>Work Link:</b>' + item.work_link.replace(',,,', nl) + nl * 2 if item.work_link else ''}"
#                                       f"{'' if not append_file_ids else '<b>Work Photo: </b>'}", parse_mode='HTML', disable_web_page_preview=True)
#             for file in append_file_ids:
#                 update.message.reply_photo(file)
#         return STEP_ENTERED
#
#
# def step_entered(update, context):
#     with Session() as session:
#         step_id = update.message.text
#         chat_data = context.chat_data
#         try:
#             step_id = int(step_id)
#             chat_data['step_id'] = step_id
#         except:
#             update.message.reply_text("Only number can be passed.")
#             return
#         gig_id = chat_data['gig_id']
#         gig = Gig.get_gig(session=session, id=gig_id)
#         global_step_to_submit = gig.steps.all()[step_id - 1].id
#         chat_data['global_id'] = global_step_to_submit
#         keyboard = [
#             [
#                 InlineKeyboardButton("Edit Comment", callback_data='editcomment'),
#                 InlineKeyboardButton("Edit Links", callback_data='editlinks'),
#                 InlineKeyboardButton("Edit Photos", callback_data='editphotos'),
#             ]
#         ]
#         reply_markup = InlineKeyboardMarkup(keyboard)
#         update.message.reply_text("Select operation using inline keyboard button.", reply_markup=reply_markup)
#         return STEP_OPERATION
#
#
# def change_record(update, context):
#     with Session() as session:
#         chat_data = context.chat_data
#         query = update.callback_query
#         query.answer()
#         if query.data == 'editcomment':
#             query.edit_message_text(text=f"Enter new comment (use /canceloperation to cancel)")
#             return SELECTED_COMMENT
#         elif query.data == 'editlinks':
#             query.edit_message_text(text="Enter work links one by one (use /canceloperation to cancel)")
#             return SELECTED_LINKS
#         elif query.data == 'editphotos':
#             query.edit_message_text(text=f"Enter new photos one by one (use /canceloperation to cancel)")
#             return SELECTED_PHOTOS
#         else:
#             query.edit_message_text(text=f"Something is wrong. Try again later.")
#             return ConversationHandler.END
#
#
# def entered_comment(update, context):
#     with Session() as session:
#         comment = update.message.text
#         chat_data = context.chat_data
#         giguser = chat_data['giguser']
#         global_id = chat_data['global_id']
#         stepgiguser = StepGigUser.get_stepgiguser_by_stepid_giguserid(session=session, stepid=global_id, giguserid=giguser.id)
#         if stepgiguser:
#             work_comment = stepgiguser.update_comment(session=session, comment=comment)
#             update.message.reply_text(f"New comment - {stepgiguser.work_comment}")
#         return ConversationHandler.END
#
#
# def entered_links(update, context):
#     link = update.message.text
#     chat_data = context.chat_data
#     if not chat_data.get('work_link'):
#         chat_data['work_link'] = list()
#     chat_data['work_link'].append(link)
#     return SELECTED_LINKS
#
#
# def complete_links(update, context):
#     with Session() as session:
#         chat_data = context.chat_data
#         if not chat_data.get('work_link'):
#             chat_data['work_links'] = None
#         else:
#             chat_data['work_links'] = ',,,'.join(chat_data['work_link'])
#         giguser = chat_data['giguser']
#         global_id = chat_data['global_id']
#         stepgiguser = StepGigUser.get_stepgiguser_by_stepid_giguserid(session=session, stepid=global_id, giguserid=giguser.id)
#         if stepgiguser:
#             links = stepgiguser.update_link(session=session, links=chat_data['work_links'])
#             update.message.reply_text(f'Updated work links - {links.work_link}')
#         return ConversationHandler.END
#
#
# def complete_photos(update, context):
#     with Session() as session:
#         chat_data = context.chat_data
#         if not chat_data.get('work_photo'):
#             chat_data['work_photos'] = None
#             logger.info(f"Inside /editsubwithgigid. /completephotos. No work photos so storing chat_data['work_photos'] to None")
#         else:
#             chat_data['work_photos'] = ',,,'.join(chat_data['work_photo'])
#         giguser = chat_data['giguser']
#         global_id = chat_data['global_id']
#         stepgiguser = StepGigUser.get_stepgiguser_by_stepid_giguserid(session=session, stepid=global_id, giguserid=giguser.id)
#         if stepgiguser:
#             photos = stepgiguser.update_photo(session=session, photos=chat_data['work_photos'])
#             update.message.reply_text(f'Updated work photos - {photos.work_photo}')
#         return ConversationHandler.END
#
#
# def only_photo_accepted(update, context):
#     update.message.reply_text("Only photos are accepted. Submit photo of your work for the respective step!")
#     return WORKPHOTO
#
#
# def entered_photos(update, context):
#     update.message.reply_text("Photo received. Processing")
#     our_file = update.effective_message.photo[-1]
#     if our_file:
#         try:
#             file_id = our_file.file_id
#             # file_unique_id = our_file.file_unique_id
#             actual_file = our_file.get_file()
#
#             filepath_to_download = actual_file['file_path']
#
#             ext = filepath_to_download.split('.')[-1]
#             filename_to_store = f"{file_id}.{ext}"
#
#             logger.info(f"Inside /submitgig. Got photo. Saving photo as- {filename_to_store}")
#             update.message.reply_chat_action(action=constants.CHATACTION_UPLOAD_PHOTO)
#
#             # status = save_file_in_s3(filepath_to_download=filepath_to_download, bucket=BUCKET_NAME,
#             # filename_to_store=filename_to_store)
#             status = save_file_locally(filepath_to_download=filepath_to_download, filename_to_store=filename_to_store)
#             if status:
#                 update.message.reply_text('Image uploaded successfully..')
#             else:
#                 update.message.reply_text("Image not uploaded. Plz try again")
#
#             chat_data = context.chat_data
#             if not chat_data.get('work_photo'):
#                 chat_data['work_photo'] = list()
#             final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
#             chat_data['work_photo'].append(final_file_path)
#             logger.info(f"Inside /submitgig. Got photo. Final work photos - {chat_data['work_photo']}")
#         except:
#             logger.error(f"Update {update} caused error WHILE SAVING PHOTO- {context.error}")
#             logger.error(f"Exception while saving photo", exc_info=True)
#     update.message.reply_text('Photo processed, successfully!')
#     return SELECTED_PHOTOS
#
#
# def canceloperation(update, context):
#     update.message.reply_text("Editing Cancelled!")
#     chat_data = context.chat_data
#     chat_data.clear()
#     return ConversationHandler.END
#
#
# if __name__ == '__main__':
#     User.__table__.create(engine, checkfirst=True)
#     Gig.__table__.create(engine, checkfirst=True)
#     Step.__table__.create(engine, checkfirst=True)
#     GigUser.__table__.create(engine, checkfirst=True)
#     StepGigUser.__table__.create(engine, checkfirst=True)
#     print_all_tables()
#
#     updater = Updater(token='2098863676:AAFJHIw5MkNnWePBzSQAMFTYrKWCCXsgplg', use_context=True)
#     # set_bot_commands(updater)
#     dp: Dispatcher = updater.dispatcher
#
#     select_option_handler = ConversationHandler(
#         entry_points=[CallbackQueryHandler(edit_option, pattern='^editdescription|editsteps|editinstructions$')],
#         states={
#             SELECTED_DESCRIPTION: [MessageHandler(Filters.text and ~Filters.command, selected_description)],
#             SELECTED_STEPS: [MessageHandler(Filters.text and ~Filters.command, selected_steps)],
#             STEP_EDITION: [MessageHandler(Filters.text and ~Filters.command, step_edition)],
#             SELECTED_INSTRUCTIONS: [MessageHandler(Filters.text and ~Filters.command, selected_instructions)]
#         },
#         fallbacks=[CommandHandler('canceledit', canceledit)],
#         map_to_parent={
#             END: ConversationHandler.END
#         }
#     )
#
#     editgig_handler = ConversationHandler(
#         entry_points=[CommandHandler('editgig', editgig)],
#         states={
#             SELECTED_OPTION: [select_option_handler]
#         },
#         fallbacks=[CommandHandler('canceledit', canceledit)],
#     )
#
#     checksubwithgigid_handle = ConversationHandler(
#         entry_points=[CommandHandler('checksubwithgigid', checksubwithgigid)],
#         states={
#             SELECTED_USER: [MessageHandler(Filters.text and ~Filters.command, selected_user)],
#             STEP_REVIEW: [MessageHandler(Filters.text and ~Filters.command, review_step)],
#             REVIEW: [MessageHandler(Filters.text and ~Filters.command, review)]
#         },
#         fallbacks=[CommandHandler('cancelprocess', cancelprocess)],
#     )
#
#     gig_create_handler = ConversationHandler(
#         entry_points=[CommandHandler('addnewgig', addnewgig)],
#         states={
#         DESC: [MessageHandler(Filters.text and ~Filters.command, desc_of_new_gig)],
#         STEPS: [MessageHandler(Filters.text and ~Filters.command, steps_of_new_gig),
#                 CommandHandler('stepdone', done_with_steps)],
#         INSTRUCTIONS: [MessageHandler(Filters.text and ~Filters.command, instructions_of_new_gig)],
#         ConversationHandler.TIMEOUT: [MessageHandler(Filters.text | Filters.command, timeout_addnewgig)]
#         },
#         fallbacks=[CommandHandler('newgigcancel', newgigcancel)],
#         conversation_timeout=addnewgig_timeout_time
#     )
#
#     submit_gig_handler = ConversationHandler(
#         entry_points=[CommandHandler('submitgig', submitgig)],
#         states={
#             WORKCOMMENT: [CommandHandler('skipcomment', skipcomment),
#                           MessageHandler(Filters.text and ~Filters.command, submit_work_comment)],
#             WORKLINK: [CommandHandler('donelinks', donelinks),
#                        MessageHandler(Filters.text and ~Filters.command, submit_work_link)],
#             WORKPHOTO: [CommandHandler('donephotos', donephotos),
#                         MessageHandler(Filters.photo, submit_work_photo),
#                         MessageHandler(Filters.text, no_text_allowed),
#                         ],
#             ConversationHandler.TIMEOUT: [MessageHandler(Filters.text | Filters.command, timeout_submitgig)]
#         },
#         fallbacks=[CommandHandler('cancelsubmission', cancelsubmission)],
#         conversation_timeout=submitgig_timeout_time
#     )
#
#     edit_record_handler = ConversationHandler(
#         entry_points=[CallbackQueryHandler(change_record, pattern='^editcomment|editlinks|editphotos$')],
#         states={
#             SELECTED_COMMENT: [MessageHandler(Filters.text and ~Filters.command, entered_comment)],
#             SELECTED_LINKS: [CommandHandler('completelinks', complete_links),
#                             MessageHandler(Filters.text and ~Filters.command, entered_links)],
#             SELECTED_PHOTOS: [CommandHandler('completephotos', complete_photos),
#                               MessageHandler(Filters.photo, entered_photos),
#                               MessageHandler(Filters.text, only_photo_accepted)]
#         },
#         fallbacks=[CommandHandler('canceloperation', canceloperation)],
#     )
#
#     editsubwithgigid_handler = ConversationHandler(
#         entry_points=[CommandHandler('editsubwithgigid', editsubwithgigid)],
#         states={
#             STEP_ENTERED: [MessageHandler(Filters.text and ~Filters.command, step_entered)],
#             STEP_OPERATION: [edit_record_handler]
#         },
#         fallbacks=[CommandHandler('canceledit', canceledit)],
#     )
#
#     dp.add_handler(CommandHandler('start', start))
#     dp.add_handler(CommandHandler('help', help))
#     dp.add_handler(CommandHandler('gigs', gigs))
#     dp.add_handler(CommandHandler('giginfo', giginfo))
#     dp.add_handler(CommandHandler('mygigs', mygigs))
#     dp.add_handler(CommandHandler('takegig', takegig))
#     dp.add_handler(CommandHandler('mygigwithans', mygigwithans))
#     dp.add_handler(submit_gig_handler)
#
#     # Admin usable conversation handler
#     dp.add_handler(editgig_handler)
#     dp.add_handler(checksubwithgigid_handle)
#     dp.add_handler(CommandHandler('checksubwithgiguserid', checksubwithgiguserid))
#     dp.add_handler(editsubwithgigid_handler)
#     dp.add_handler(gig_create_handler)
#
#     dp.add_error_handler(error)
#     dp.add_handler(MessageHandler(Filters.text, anyrandom))
#     updater.start_polling()
#     updater.idle()
#
#
#



# //////////////////////////////////////////////////////////////////////////////////////////////

# from telegram import constants
# from telegram.ext import Updater, Dispatcher, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackContext
# from models import User, Gig, Step, GigUser, StepGigUser
# from dbhelper import Session, engine
# from datetime import datetime
# import logging
# import boto3
# import os
# from dotenv import load_dotenv
# import requests
# from botocore.exceptions import NoCredentialsError
# from telegram.bot import BotCommand
# from bot_commands import suggested_commands
#
# load_dotenv()
#
# log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# logging.basicConfig(format=log_format, level=logging.INFO)
# logger = logging.getLogger(__name__)
#
# # TOKEN = os.getenv('CTOGIGS_TELEGRAM_TOKEN')
# # TOKEN = '2098863676:AAEiJQ0KExb_SwFQoRrpFIMkcu1Cz_Itb3U'
# TOKEN = '2098863676:AAFJHIw5MkNnWePBzSQAMFTYrKWCCXsgplg'
# show_all_gigs_limit = 5
# DESC, STEPS, INSTRUCTIONS = range(3)
# WORKCOMMENT, WORKLINK, WORKPHOTO = range(3)
# ADMIN_CHAT_IDS = [1066103338]
#
# submitgig_timeout_time = 120
# addnewgig_timeout_time = 120
#
# FOLDERNAME_USERWORKS = 'userworks/'
# if not os.path.isdir(FOLDERNAME_USERWORKS):
#     os.mkdir(FOLDERNAME_USERWORKS)
#
# BUCKET_NAME = 'work-photos-ctogigsbot'
#
#
# def save_file_in_s3(filepath_to_download, bucket, filename_to_store):
#     s3 = boto3.client('s3', region_name='us-east-1')
#     # print(type(s3))
#     try:
#         logger.info(f"Inside /addlog. Saving image on S3")
#         imageResponse = requests.get(filepath_to_download, stream=True).raw
#         final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
#         s3.upload_fileobj(imageResponse, bucket, final_file_path)
#         logger.info("Image Saved on S3..")
#         return True
#     except FileNotFoundError:
#         logger.error('File not found..')
#         return False
#     except NoCredentialsError:
#         logger.info('Credentials not available')
#         return False
#     except:
#         logger.info('Some other error saving the file to S3')
#
#
# def start(update, context):
#     logging.info('Inside start')
#     first_name = update.message.from_user.first_name
#     last_name = update.message.from_user.last_name
#     chat_id = update.message.chat_id
#     tg_username = None
#     if update.message.from_user.username:
#         tg_username = update.message.from_user.username
#     created_at = datetime.now()
#     with Session() as session:
#         user = User.get_user_by_chatid(session=session, chat_id=chat_id)
#         if not user:
#             user = User(chat_id=chat_id, first_name=first_name, last_name=last_name, tg_username=tg_username,
#                         created_at=created_at)
#             session.add(user)
#             try:
#                 session.commit()
#                 update.message.reply_text(f"Welcome to CTOlogs, {user.first_name.title()}")
#             except:
#                 session.rollback()
#         else:
#                 update.message.reply_text(f"Welcome back, {user.first_name.title()}")
#
#
# def help(update, context):
#     update.message.reply_text('This bot allows you to explore and register for <b><i>python/fullstack/ml-dl-nlp/blockchain</i></b> related gigs. '
#                               '\n\nUse / to see list of all supported/usable commands!', parse_mode='HTML')
#
#
# def gigs(update, context):
#     with Session() as session:
#         user = get_current_user(session=session, update=update)
#         if not user:
#             return
#         all_gigs = session.query(Gig).order_by(Gig.created_at.desc()).limit(show_all_gigs_limit).all()
#         update.message.reply_text(f'Showing latest {show_all_gigs_limit} gigs\n'
#                                   f"Use <i>/giginfo 3</i> to check gig with 3", parse_mode='HTML')
#         for gig in all_gigs:
#             nl = '\n\n'
#             final_steps = nl.join([f"{_id+1}. {step.step_text}" for _id, step in enumerate(gig.steps.all())])
#             update.message.reply_text(f"<b>Gig Id:</b> {gig.id}\n\n"
#                                       f"<b>Desc:</b> {gig.short_description}\n\n"
#                                       f"<b>Steps:</b> \n{final_steps}\n\n"
#                                       f"<b>Instructions:</b> {gig.instructions}", parse_mode='HTML')
#
#
# def takegig(update, context):
#     with Session() as session:
#         current_user = get_current_user(update=update, session=session)
#         if not current_user:
#             return
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                      '<i>e.g. /takegig 1 or /takegig 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#
#         current_gig = Gig.get_gig(session=session, id=recv_id)
#         if not current_gig:
#             update.message.reply_text('Such a gig does not exist!')
#             return
#         current_user.gigusers.append(GigUser(gig_id=recv_id))
#         session.add(current_user)
#         try:
#             session.commit()
#         except:
#             session.rollback()
#             update.message.reply_text('Something went wrong. Please try again!')
#             return
#         else:
#             update.message.reply_text(f'You have signed up for Gig {recv_id}.\n'
#                                       f' Check /mygigs for details.')
#
#
# def giginfo(update, context):
#     with Session() as session:
#         user = get_current_user(session=session, update=update)
#         if not user:
#             return
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                       '<i>e.g. /giginfo 1 or /giginfo 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text(f"Gig with id - {recv_id} does not exist")
#         else:
#             nl = '\n\n'
#             final_steps = nl.join([f"{_id + 1}. {step.step_text}" for _id, step in enumerate(gig.steps.all())])
#             update.message.reply_text(f"<b>Gig Id:</b> {gig.id}\n\n"
#                                       f"<b>Desc:</b> {gig.short_description}\n\n"
#                                       f"<b>Steps:</b> \n{final_steps}\n\n"
#                                       f"<b>Instructions:</b> {gig.instructions}", parse_mode='HTML')
#
#
# def mygigs(update, context):
#     with Session() as session:
#         current_user = get_current_user(session=session, update=update)
#         if not current_user:
#             return
#         nl = '\n\n'
#         if not current_user.gigs:
#             update.message.reply_text("You haven't taken up any gigs yet!")
#             return
#         update.message.reply_text('You have registered for the following gigs')
#         for gig in current_user.gigs:
#             update.message.reply_text(f"Gig Id: {gig.id}\n\n"
#                                       f"Desc: {gig.short_description}\n\n"
#                                       f"Steps:\n{nl.join([step.step_text for step in gig.steps.all()])}")
#
#
# def addnewgig(update, context):
#     chat_id = update.message.chat_id
#     if chat_id not in ADMIN_CHAT_IDS:
#         update.message.reply_text('You do not have access to do this command')
#         return
#     update.message.reply_text("Alright, let's add a new gig. Write description in short.\n"
#                               "Use /newgigcancel to cancel.")
#     return DESC
#
#
# def desc_of_new_gig(update, context: CallbackContext):
#     description = update.message.text
#     chat_data = context.chat_data
#     chat_data['desc'] = description
#     update.message.reply_text("Got the description. Write steps one by one.\n"
#                               "Use /stepdone when done.")
#     return STEPS
#
#
# def steps_of_new_gig(update, context):
#     steps = update.message.text
#     chat_data = context.chat_data
#     if not chat_data.get('steps'):
#         chat_data['steps'] = list()
#     chat_data['steps'].append(steps)
#     return STEPS
#
#
# def done_with_steps(update, context):
#     update.message.reply_text("Noted the steps. Any instructions?")
#     return INSTRUCTIONS
#
#
# def instructions_of_new_gig(update, context):
#     instructions = update.message.text
#     update.message.reply_text("That's it!")
#     chat_data = context.chat_data
#     chat_data['instructions'] = instructions
#     save_new_gig(update, context)
#     return ConversationHandler.END
#
#
# def save_new_gig(update, context):
#     chat_id = update.message.chat_id
#     chat_data = context.chat_data
#     short_description = chat_data['desc']
#     instructions = chat_data['instructions']
#     steps = chat_data['steps']
#     owner_chat_id = chat_id
#     gig = Gig(short_description=short_description, instructions=instructions, owner_chat_id=owner_chat_id, created_at=datetime.now(), updated_at=datetime.now())
#     with Session() as session:
#         session.add(gig)
#         try:
#             session.commit()
#             update.message.reply_text(f'Gig created, {gig}')
#         except:
#             session.rollback()
#         for localstepid,step in enumerate(steps):
#             step_obj = Step(localstepid=localstepid + 1, gig_id=gig.id, step_text=step)
#             session.add(step_obj)
#         try:
#             session.commit()
#             chat_data.clear()
#             logger.info('chat_data cleared')
#         except:
#             session.rollback()
#
#
# def newgigcancel(update, context):
#     update.message.reply_text("Cancelled adding new gig")
#     chat_data = context.chat_data
#     chat_data.clear()
#     return ConversationHandler.END
#
#
# def anyrandom(update, context):
#     update.message.reply_text("Sorry, I am new to understand this!")
#
#
# def error(update, context: CallbackContext):
#     logger.warning(f'Update {update} caused an error {context.error}')
#
#
# def print_all_tables():
#     with Session() as session:
#         print([user for user in session.query(User).all()])
#         print([gig for gig in session.query(Gig).all()])
#         print([step for step in session.query(Step).all()])
#         print([giguser for giguser in session.query(GigUser).all()])
#         print([stepgiguser for stepgiguser in session.query(StepGigUser).all()])
#         # last_step = session.query(Step).all()[-1]
#         # print(last_step)
#         # print(last_step.gig)
#         # print(last_step.gig.short_description)
#         # user1 = session.query(User).all()[0]
#         # user1.gigusers.append(GigUser(gig_id=gig2.id))
#         # print(user1.gigs)
#         # gig2 = session.query(Gig).all()[1]
#         # global_step_to_submit = gig2.steps.all()[0].id
#         # print(gig2.steps.all())
#         # print(gig2.short_description)
#         # print(gig2.users)
#         # gu = GigUser(gig_id=gig2.id, taken_at=datetime.utcnow())
#         # gu = session.query(GigUser).all()[0]
#         # user1.gigusers.remove(gu)
#         # session.add(user1)
#         # try:
#         #     session.commit()
#         # except:
#         #     session.rollback()
#
#
# def get_current_user(session, update):
#     chat_id = update.message.chat_id
#     user = User.get_user_by_chatid(session=session, chat_id=chat_id)
#     if user:
#         return user
#     else:
#         update.message.reply_text('Use /start first then use this command again!')
#         return None
#
#
# def save_file_locally(filepath_to_download, filename_to_store):
#     response = requests.get(filepath_to_download)
#     final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
#     try:
#         logger.info(f"Inside /addlog. Saving image locally")
#         with open(final_file_path, 'wb') as f:
#             f.write(response.content)
#         logger.info("Image Saved locally..")
#         return True
#     except:
#         logger.info("Image could not be saved locally..")
#         return False
#
#
# def submitgig(update, context):
#     with Session() as session:
#         user = get_current_user(session=session, update=update)
#         if not user:
#             return
#         if not context.args:
#             update.message.reply_text("You need to pass gig_id next to the command.")
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number is allowed next to the command.')
#             return
#         gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text("This is not a valid gig!")
#             return
#         giguser = GigUser.get_giguser_by_gigid_userid(session=session, userid=user.id, gigid=gig.id)
#         if not giguser:
#             update.message.reply_text(f"You need to TAKE this gig first. Use '/takegig {gig.id}' to register for that gig!")
#             return
#         # update.message.reply_text(f"Alright, accepting your work for Gig #{recv_id} \n(Use /cancelsubmission to cancel.)")
#         steps_submitted = giguser.stepgigusers.all()
#         global_step_to_submit = gig.steps.all()[0].id
#         local_step_to_submit = gig.steps.filter(Step.id == global_step_to_submit).first().localstepid
#
#         if not steps_submitted and local_step_to_submit == 1:
#             update.message.reply_text(
#                 f'Accepting your work for <b>Step {local_step_to_submit} (global step id {global_step_to_submit})</b> of <b>Gig {recv_id}</b>\n'
#                 f'(Use /cancelsubmission to cancel submission of step.)\n\n'
#                 f'This is FIRST STEP for which you are submitting your work!\n'
#                 f'Write comment if any, /skipcomment to skip.\n', parse_mode='HTML')
#         else:
#             steps_submitted_list = [stepgiguser.step_id for stepgiguser in steps_submitted]
#             last_step_submitted = max(steps_submitted_list)
#             last_step_of_gig = gig.steps.all()[-1].id
#             if last_step_submitted == last_step_of_gig:
#                 update.message.reply_text("You have submitted all the steps! No more steps left. Your gig submission is complete!")
#                 return
#             elif last_step_submitted < last_step_of_gig:
#                 global_step_to_submit = max(steps_submitted_list) + 1
#             update.message.reply_text(f"You have already submitted your work for step #{local_step_to_submit} (global step id #{global_step_to_submit - 1})!\n"
#                                       f"(Use /cancelsubmission to cancel.)\n\n"
#                                       f"Submit your work for {local_step_to_submit + 1} (global step id {global_step_to_submit}) step now.\n"
#                                       f"Write comment if any, /skipcomment to skip.")
#
#         chat_data = context.chat_data
#         chat_data['giguser_id'] = giguser.id
#         chat_data['global_step_to_submit'] = global_step_to_submit
#         # local_step_to_submit = Gig.get_gig(session=session, id=global_step_to_submit).localstepid
#     return WORKCOMMENT
#
#
# def submit_work_comment(update, context):
#     chat_data = context.chat_data
#     work_comment = update.message.text
#     chat_data['work_comment'] = work_comment
#     update.message.reply_text("Got your comment.\n"
#                               "Share github/drive/youtube link that points to your code or video demonstration of the step/code.\n"
#                               "Use /donelinks once done")
#     return WORKLINK
#
#
# def submit_work_link(update, context):
#     link = update.message.text
#     chat_data = context.chat_data
#     if not chat_data.get('work_link_temp'):
#         chat_data['work_link_temp'] = list()
#     chat_data['work_link_temp'].append(link)
#     return WORKLINK
#
#
# def submit_work_photo(update, context):
#     update.message.reply_text("Photo received. Processing")
#     our_file = update.effective_message.photo[-1]
#     if our_file:
#         try:
#             file_id = our_file.file_id
#             # file_unique_id = our_file.file_unique_id
#             actual_file = our_file.get_file()
#
#             filepath_to_download = actual_file['file_path']
#
#             ext = filepath_to_download.split('.')[-1]
#             filename_to_store = f"{file_id}.{ext}"
#
#             logger.info(f"Inside /submitgig. Got photo. Saving photo as- {filename_to_store}")
#             update.message.reply_chat_action(action=constants.CHATACTION_UPLOAD_PHOTO)
#
#             # status = save_file_in_s3(filepath_to_download=filepath_to_download, bucket=BUCKET_NAME,
#                                      # filename_to_store=filename_to_store)
#             status = save_file_locally(filepath_to_download=filepath_to_download, filename_to_store=filename_to_store)
#             if status:
#                 update.message.reply_text('Image uploaded successfully..')
#             else:
#                 update.message.reply_text("Image not uploaded. Plz try again")
#
#             chat_data = context.chat_data
#             if not chat_data.get('work_photo_temp'):
#                 chat_data['work_photo_temp'] = list()
#             final_file_path = f"{FOLDERNAME_USERWORKS}{filename_to_store}"
#             chat_data['work_photo_temp'].append(final_file_path)
#             logger.info(f"Inside /submitgig. Got photo. Final work photos - {chat_data['work_photo_temp']}")
#         except:
#             logger.error(f"Update {update} caused error WHILE SAVING PHOTO- {context.error}")
#             logger.error(f"Exception while saving photo", exc_info=True)
#     update.message.reply_text('Photo processed, successfully!')
#     return WORKPHOTO
#
#
# def skipcomment(update, context):
#     update.message.reply_text('Skipping comment.')
#     chat_data = context.chat_data
#     chat_data['work_comment'] = None
#     update.message.reply_text("Share github/drive/youtube link that points to your code or video demonstration of the step/code.\n"
#                               "Use /donelinks once done")
#     return WORKLINK
#
#
# def no_text_allowed(update, context):
#     update.message.reply_text("Only photos are accepted. Submit photo of your work for the respective step!")
#     return WORKPHOTO
#
#
# def donelinks(update, context):
#     chat_data = context.chat_data
#     if not chat_data.get('work_link_temp'):
#         chat_data['work_links'] = None
#     else:
#         chat_data['work_links'] = ',,,'.join(chat_data['work_link_temp'])
#     update.message.reply_text('Next, upload photos of code/output if any.\n'
#                         'Use /donephotos once done')
#     return WORKPHOTO
#
#
# def donephotos(update, context):
#     chat_data = context.chat_data
#     if not chat_data.get('work_photo_temp'):
#         chat_data['work_photos'] = None
#         logger.info(f"Inside /submitgig. /donephotos. No work photos so storing chat_data['work_photos'] to None")
#     else:
#         chat_data['work_photos'] = ',,,'.join(chat_data['work_photo_temp'])  # deliberately using this instead of comma, bcz if user somehow enters , in his work links, then it'll be split unnecessarily. so we want some unique identifier.
#
#     status = save_gig_submission(update, context)
#     if status:
#         update.message.reply_text('Submitted the gig successfully.\n'
#                         'Check /mygigwithans for more details.')
#     else:
#         update.message.reply_text("Something went wrong. Please submit the work for this step again.")
#     return ConversationHandler.END
#
#
# def cancelsubmission(update, context):
#     update.message.reply_text('Gig submission cancelled.')
#     return ConversationHandler.END
#
#
# def save_gig_submission(update, context):
#     chat_data = context.chat_data
#     giguser_id = chat_data['giguser_id']
#     step_id = chat_data['global_step_to_submit']
#     work_comment = chat_data['work_comment']
#     work_links = chat_data['work_links']
#     work_photos = chat_data['work_photos']
#     update.message.reply_text('Alright. Saving your record')
#
#     stepgiguser = StepGigUser(step_id=step_id, giguser_id=giguser_id, work_comment=work_comment, work_photo=work_photos, work_link=work_links, submitted_at=datetime.now())
#     with Session() as session:
#         session.add(stepgiguser)
#         try:
#             session.commit()
#             update.message.reply_text(f'StepGigUser created, {stepgiguser}')
#             chat_data.clear()
#             logger.info('chat_data cleared')
#         except:
#             update.message.reply_text("Something went wrong")
#             session.rollback()
#     return True
#
#
# def mygigwithans(update, context):
#     with Session() as session:
#         user: User = get_current_user(session=session, update=update)
#         if not user:
#             return
#         if not context.args:
#             update.message.reply_text('You need to pass gig id next to the command.\n'
#                                       '<i>e.g. /mygigwithans 1 or /mygigwithans 2</i>', parse_mode='HTML')
#             return
#         recv_id = context.args[0]
#         try:
#             recv_id = int(recv_id)
#         except:
#             update.message.reply_text('Only number can be passed. Text not allowed.')
#             return
#         gig: Gig = Gig.get_gig(session=session, id=recv_id)
#         if not gig:
#             update.message.reply_text(f"Gig with id - {recv_id} does not exist")
#             return
#         else:
#             giguser = GigUser.get_giguser_by_gigid_userid(session=session, gigid=gig.id, userid=user.id)
#             if not giguser:
#                 update.message.reply_text(f"You haven't take gig #{recv_id}.\nUse /takegig {recv_id} to take gig.")
#                 return
#             for _id, item in enumerate(giguser.stepgigusers.all()):
#                 append_file_ids = []
#                 if item.work_photo:
#                     photos = item.work_photo.split(',,,')
#                     for photo in photos:
#                         if photo.find('userworks/') != -1:
#                             file_id = photo.split('userworks/')[-1].split('.')[0]
#                             append_file_ids.append(file_id)
#                 nl = '\n'
#                 update.message.reply_text(f"<b>Step Id:</b> {_id + 1}\n\n"
#                                           f"<b>Submitted at:</b> {item.submitted_at.strftime('%d %b %Y, %I:%M %p')}\n\n"
#                                           f"{'<b>Work Comment:</b>' + item.work_comment + nl*2 if item.work_comment else ''}"
#                                           f"{'<b>Work Link:</b>' + item.work_link.replace(',,,', nl) + nl*2 if item.work_link else ''}"
#                                           f"{'' if not append_file_ids else '<b>Work Photo: </b>'}", parse_mode='HTML', disable_web_page_preview=True)
#                 for file in append_file_ids:
#                     update.message.reply_photo(file)
#
#
# def set_bot_commands(updater):
#     commands = [BotCommand(key, val) for key, val in dict(suggested_commands).items()]
#     updater.bot.set_my_commands(commands)
#
#
# def timeout_submitgig(update, context):
#     with Session() as session:
#         update.message.reply_text(f'Timeout. Use /submitgig again to submit step of gig. (Timeout limit - {submitgig_timeout_time} sec)')
#         chat_data = context.chat_data
#         chat_data.clear()
#         logger.info(f"Timeout for /submitgig")
#         return ConversationHandler.END
#
#
# def timeout_addnewgig(update, context):
#     with Session() as session:
#         update.message.reply_text(f'Timeout. Use /addnewgig again to submit step of gig. (Timeout limit - {addnewgig_timeout_time} sec)')
#         chat_data = context.chat_data
#         chat_data.clear()
#         logger.info(f"Timeout for /addnewgig")
#         return ConversationHandler.END
#
#
# if __name__ == '__main__':
#     User.__table__.create(engine, checkfirst=True)
#     Gig.__table__.create(engine, checkfirst=True)
#     Step.__table__.create(engine, checkfirst=True)
#     GigUser.__table__.create(engine, checkfirst=True)
#     StepGigUser.__table__.create(engine, checkfirst=True)
#     print_all_tables()
#
#     updater = Updater(token='2098863676:AAFJHIw5MkNnWePBzSQAMFTYrKWCCXsgplg', use_context=True)
#     # set_bot_commands(updater)
#     dp: Dispatcher = updater.dispatcher
#     dp.add_handler(CommandHandler('start', start))
#     dp.add_handler(CommandHandler('help', help))
#     dp.add_handler(CommandHandler('gigs', gigs))
#     dp.add_handler(CommandHandler('giginfo', giginfo))
#     dp.add_handler(CommandHandler('mygigs', mygigs))
#     dp.add_handler(CommandHandler('takegig', takegig))
#     dp.add_handler(CommandHandler('mygigwithans', mygigwithans))
#     gig_create_handler = ConversationHandler(
#         entry_points=[CommandHandler('addnewgig', addnewgig)],
#         states={
#         DESC: [MessageHandler(Filters.text and ~Filters.command, desc_of_new_gig)],
#         STEPS: [MessageHandler(Filters.text and ~Filters.command, steps_of_new_gig),
#                 CommandHandler('stepdone', done_with_steps)],
#         INSTRUCTIONS: [MessageHandler(Filters.text and ~Filters.command, instructions_of_new_gig)],
#         ConversationHandler.TIMEOUT: [MessageHandler(Filters.text | Filters.command, timeout_addnewgig)]
#         },
#         fallbacks=[CommandHandler('newgigcancel', newgigcancel)],
#         conversation_timeout=addnewgig_timeout_time
#     )
#
#     submit_gig_handler = ConversationHandler(
#         entry_points=[CommandHandler('submitgig', submitgig)],
#         states={
#             WORKCOMMENT: [CommandHandler('skipcomment', skipcomment),
#                           MessageHandler(Filters.text and ~Filters.command, submit_work_comment)],
#             WORKLINK: [CommandHandler('donelinks', donelinks),
#                        MessageHandler(Filters.text and ~Filters.command, submit_work_link)],
#             WORKPHOTO: [CommandHandler('donephotos', donephotos),
#                         MessageHandler(Filters.photo, submit_work_photo),
#                         MessageHandler(Filters.text, no_text_allowed)],
#             ConversationHandler.TIMEOUT: [MessageHandler(Filters.text | Filters.command, timeout_submitgig)]
#         },
#         fallbacks=[CommandHandler('cancelsubmission', cancelsubmission)],
#         conversation_timeout=submitgig_timeout_time
#     )
#     dp.add_handler(gig_create_handler)
#     dp.add_handler(submit_gig_handler)
#     dp.add_error_handler(error)
#     dp.add_handler(MessageHandler(Filters.text, anyrandom))
#     updater.start_polling()
#     updater.idle()
#
#
#
# # ==========================================================================================================
#
# # import requests
# # from sqlalchemy.sql.functions import session_user
# # # from sqlalchemy.sql.functions import session_user
# # # from sqlalchemy.util.langhelpers import _update_argspec_defaults_into_env
# # from telegram import Update
# # from telegram.ext import Updater, Dispatcher, CommandHandler, commandhandler, ConversationHandler, MessageHandler, \
# #     Filters, CallbackContext
# # from models import User, Gig, Step, GigUser, StepUser
# # from dbhelper import Session, engine
# # from datetime import datetime
# # import logging
# #
# # # /gigs -> send list of gigs
# # # /mygigs ->send list of gigs
# # # /gigscounts ->total gigs on the system
# #
# # log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# # logging.basicConfig(format=log_format, level=logging.INFO)
# # logger = logging.getLogger(__name__)
# #
# # TOKEN = '2098863676:AAEiJQ0KExb_SwFQoRrpFIMkcu1Cz_Itb3U'
# # show_all_gigs_limit = 5
# # DESC, STEPS, INSTRUCTIONS = range(3)
# # ADMIN_CHAT_IDS = [1066103338]
# #
# #
# # def start(update, context):
# #     logger.info('Inside Start')
# #     #  print_data(update,context)
# #     first_name = update.message.from_user.first_name
# #     last_name = update.message.from_user.last_name
# #     chat_id = update.message.chat_id
# #     tg_username = None
# #     if update.message.from_user.username:
# #         tg_username = update.message.from_user.username
# #     created_at = datetime.now()
# #     # print(first_name)
# #
# #     with Session() as session:
# #         user = User.get_user_by_chatid(session=session, chat_id=chat_id)
# #         if not user:
# #             # print('no such user')
# #             user = User(chat_id=chat_id, first_name=first_name, last_name=last_name, tg_username=tg_username,
# #                         created_at=created_at)
# #             session.add(user)
# #             try:
# #                 session.commit()
# #                 update.message.reply_text(f"Welcome to CTOlogs,{user.first_name.title()}")
# #             except:
# #                 # print('Inside exception')
# #                 session.rollback()
# #         else:
# #             update.message.reply_text(f"welcome back,{user.first_name.title()}")
# #
# #
# # def help(update, context):
# #     update.message.reply_text(
# #         ' This bot  allows  you to explore  and register  for <i>python/full stack</i> related gigs.\n'
# #         ' Use / to get a list j of all supported commands .', parse_mode='HTML')
# #
# #
# # def gigs(update, context):
# #     with Session() as session:
# #         all_gigs = session.query(Gig).order_by(Gig.created_at.desc()).limit(show_all_gigs_limit).all()
# #         update.message.reply_text(f'Showing latest {show_all_gigs_limit} gigs.\n'
# #                                   f'<i>Use /giginfo 3</i> to check gig with id 3', parse_mode='HTML')
# #         print(all_gigs)
# #         for gig in all_gigs:
# #             # f"<b>Steps</b>:{gig.steps.all()}")
# #             # final_steps = ''
# #             # for step in gig.steps.all():
# #             #   final_steps +=f"{step.step_text}\n\n"
# #             # update.message.reply_text(final_steps)
# #             nl = '\n\n'
# #             final_steps = nl.join([f"{_id + 1} - {step.step_text}" for _id, step in enumerate(gig.steps.all())])
# #             update.message.reply_text(f"<b>Gig Id </b>:{gig.id}:\n\n"
# #                                       f"<b>Desc</b>:{gig.short_description}\n\n"
# #                                       f"<b>Steps:</b>\n{final_steps}\n\n"
# #                                       f"<b>Instructions:</b>{gig.instructions}", parse_mode='HTML')
# #
# #
# # # update.message.reply_text('Gig2 -Write a simple telegram bot with /start command ')
# #
# # def takethisgig(update, context):
# #     if not context.args:
# #         update.message.reply_text('You need pass gig id next to the command .e.g.\n'
# #                                   '<i>/takethisgig 1 .\n /takethisgig 2</i>', parse_mode='HTML')
# #         return
# #     recv_id = context.args[0]
# #     try:
# #         recv_id = int(recv_id)
# #     except:
# #         update.message.reply_text('Only  number  can be passed .Text not allowed.')
# #         return
# #     with Session() as session:
# #         current_user = get_current_user(session=session, update=update)
# #         if not current_user:
# #             return
# #         current_gig = Gig.get_gig(session=session, id=recv_id)
# #         if not current_gig:
# #             update.message.reply_text('Such a gig does not exist!')
# #             return
# #         current_user.gigusers.append(GigUser(gig_id=recv_id))
# #         session.add(current_user)
# #         try:
# #             session.commit()
# #         except:
# #             session.rollback()
# #             update.message.reply_text('Something went wrong. Please try again!')
# #             return
# #         else:
# #             update.message.reply_text(f'You have signed up for Gig {recv_id}\n'
# #                                       f'Check /mygigs for details.')
# #
# # def giginfo(update, context):
# #     if not context.args:
# #         update.message.reply_text('You need pass gig id next to the command .e.g.\n'
# #                                   '<i>/giginfo 1 .\n /giginfo 2</i>', parse_mode='HTML')
# #         return
# #     recv_id = context.args[0]
# #     try:
# #         recv_id = int(recv_id)
# #     except:
# #         update.message.reply_text('Only  number  can be passed .Text not allowed.')
# #         return
# #     with Session() as session:
# #         gig = Gig.get_gig(session=session, id=recv_id)
# #         if not gig:
# #             update.message.reply_text(f'Gig with id -{recv_id} does not exist')
# #         else:
# #             nl = '\n\n'
# #             final_steps = nl.join([f"{_id + 1}{step.step_text}" for _id, step in enumerate(gig.steps.all())])
# #             update.message.reply_text(f"<b>Gig Id </b>:{gig.id}:\n\n"
# #                                       f"<b>Desc</b>:{gig.short_description}\n\n"
# #                                       f"<b>Steps:</b>\n{final_steps}\n\n"
# #                                       f"<b>Instructions:</b>{gig.instructions}", parse_mode='HTML')
# #
# #
# # # print(context.args)
# #
# # def mygigs(update, context):
# #     with Session() as session:
# #         current_user = get_current_user(session=session, update=update)
# #         if not current_user:
# #             return
# #         nl='\n\n'
# #         if not current_user.gigs:
# #             update.message.reply_text("You haven't taken up any gigs yet!")
# #             return
# #         update.message.reply_text('You have registered for the following gigs')
# #         for gig in current_user.gigs:
# #             update.message.reply_text(f"Gig Id: {gig.id}\n\n"
# #                                       f"Desc: {gig.short_description}\n\n"
# #                                       f"Steps: \n{nl.join([step.step_text for step in gig.steps.all()])}")
# #         # current_user.gigs
# #
# #
# #
# # # TODO -only admin should  be run this command
# #
# # def addnewgig(update, context):
# #     chat_id = update.message.chat_id
# #     if not chat_id in ADMIN_CHAT_IDS:
# #         update.message.reply_text('You do not have access to this command!')
# #         return
# #     update.message.reply_text("Alrights ,lets add  a new  gig .Write description in short.\n"
# #                               "Use /newgigcancel to cancel.")
# #
# #     return DESC
# #
# #
# # def desc_of_new_gig(update, context: CallbackContext):
# #     description = update.message.text
# #     chat_data = context.chat_data
# #     chat_data['desc'] = description
# #     print(description)
# #     update.message.reply_text("Got the description ,Write  steps one by one,\n"
# #                               "Use /stepsdone  when done.")
# #     return STEPS
# #
# #
# # def steps_of_new_gig(update, context):
# #     steps = update.message.text
# #     print(steps)
# #     chat_data = context.chat_data
# #     # update.message.reply_text('Got step,Any instructions?')
# #     if not chat_data.get('steps'):
# #         chat_data['steps'] = list()
# #         chat_data['steps'].append(steps)
# #     else:
# #         chat_data['steps'].append(steps)
# #
# #     # chat_data['steps']=steps
# #     return STEPS
# #
# #
# # def done_with_steps(update, context):
# #     update.message.reply_text('Noted the steps,Any instructions?')
# #     return INSTRUCTIONS
# #
# #
# # def instructions_of_new_gig(update, context):
# #     instructions = update.message.text
# #
# #     update.message.reply_text('Thats it!')
# #     chat_data = context.chat_data
# #     chat_data['instructions'] = instructions
# #     # print(chat_data)
# #
# #     save_new_gig(update, context)
# #     return ConversationHandler.END
# #
# #
# # def save_new_gig(update, context):
# #     chat_id = update.message.chat_id
# #     chat_data = context.chat_data
# #     short_description = chat_data['desc']
# #     instructions = chat_data['instructions']
# #     steps = chat_data['steps']
# #     # owner_chat_id = chat_id
# #     gig = Gig(short_description=short_description, instructions=instructions, owner_chat_id=chat_id,
# #               created_at=datetime.now(), updated_at=datetime.now())
# #     with Session() as session:
# #         session.add(gig)
# #         try:
# #             session.commit()
# #             # step=Step(gig_id=gig.id,step_text=steps)
# #             update.message.reply_text(f"Gig created - {gig}")
# #
# #         except:
# #             session.rollback()
# #
# #         for step in steps:
# #             # print(gig.id)
# #             step_obj = Step(gig_id=gig.id, step_text=step)
# #             session.add(step_obj)
# #         try:
# #             session.commit()
# #             chat_data.clear()
# #             logger.info('chat_data cleared')
# #
# #         except:
# #             session.rollback()
# #
# #     # print(chat_data)
# #
# #
# # def newgigcancel(update, context):
# #     update.message.reply_text('Cancelled adding new gig')
# #     chat_data = context.chat_data
# #     chat_data.clear()
# #     return ConversationHandler.END
# #
# #
# # def anyrandom(update, context):
# #     update.message.reply_text("Sorry,I am too new to this to understand!")
# #
# #
# # def print_all_tables():
# #     with Session() as session:
# #         print([user for user in session.query(User).all()])
# #         print([gig for gig in session.query(Gig).all()])
# #         print([step for step in session.query(Step).all()])
# #         print([giguser for giguser in session.query(GigUser).all()])
# #         user1 = session.query(User).all()[0]
# #         print(user1)
# #         gig2 = session.query(Gig).all()[1]
# #         print(gig2)
# #         # gu = GigUser(gig_id=gig1.id, taken_at=datetime.utcnow())
# #         # user1.gigusers.append(GigUser(gig_id=gig1.id))
# #         # gu = session.query(GigUser).all()[0]
# #         # user1.gigusers.remove(gu)
# #         # session.add(user1)
# #         # try:
# #         #     session.commit()
# #         # except:
# #         #     session.rollback()
# #         print(user1.gigusers.all())
# #         print(gig2.gigusers.all())
# #         print('===============================')
# #         print(user1.gigs)
# #         print(gig2.users)
# #
# #         # gig1 =session.query(Gig).all()[0]
# #         # print(gig1)
# #         # print(gig1.short_description)
# #         # print(gig1.steps.all())
# #         # last_step=session.query(Step).all()[-1]
# #         # print(last_step)
# #         # print(last_step.gig)
# #         # print(last_step.gig.short_description)
# #
# #         # print(Session.query(User).all())
# #     # print(Session.query(Gig).all())
# #
# # def get_current_user(session, update):
# #     chat_id = update.message.chat_id
# #     user = User.get_user_by_chatid(session=session, chat_id=chat_id)
# #     if user:
# #         return user
# #     else:
# #         update.message.reply_text('Use /start first then use this command again!')
# #         return None
# #
# # def error(update, context):
# #     logger.warning(f"Update {update} caused an error {context.error}")
# #
# #
# # if __name__ == '__main__':
# #     # print(datetime.utcnow())
# #     User.__table__.create(engine, checkfirst=True)
# #     Gig.__table__.create(engine, checkfirst=True)
# #     Step.__table__.create(engine, checkfirst=True)
# #     GigUser.__table__.create(engine, checkfirst=True)
# #     StepUser.__table__.create(engine, checkfirst=True)
# #     print_all_tables()
# #
# #     updater = Updater(token=TOKEN, use_context=True)
# #     dp: Dispatcher = updater.dispatcher
# #     dp.add_handler(CommandHandler('start', start))
# #     dp.add_handler(CommandHandler('help', help))
# #     dp.add_handler(CommandHandler('gigs', gigs))
# #     dp.add_handler(CommandHandler('giginfo', giginfo))
# #     dp.add_handler(CommandHandler('mygigs', mygigs))
# #     dp.add_handler(CommandHandler('takethisgig', takethisgig))
# #     gig_create_handler = ConversationHandler(
# #         entry_points=[CommandHandler('addnewgig', addnewgig)],
# #         states={
# #             DESC: [MessageHandler(Filters.text and ~Filters.command, desc_of_new_gig)],
# #             STEPS: [MessageHandler(Filters.text and ~Filters.command, steps_of_new_gig),
# #                     CommandHandler('stepsdone', done_with_steps)],
# #             INSTRUCTIONS: [MessageHandler(Filters.text and ~Filters.command, instructions_of_new_gig)],
# #         },
# #         fallbacks=[CommandHandler('newgigcancel', newgigcancel)]
# #     )
# #     dp.add_handler(gig_create_handler)
# #     dp.add_error_handler(error)
# #     dp.add_handler(MessageHandler(Filters.text, anyrandom))
# #     updater.start_polling()
# #     updater.idle()
# #
# # # TO Do
# #
# # # 1./ addnewgig - admin that command should store  new gig details in gig table (id ,description ,steps,)
# # # 2.The command should be conversational command
# # # 3. Create tables Gigs and Steps with one  to many
# #
# #
# #
# #
# #
# #
# #
