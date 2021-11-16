import datetime
import os
import pickle
import urllib.parse
import urllib.request as request
from collections import Counter
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import tika
import wget
from dateutil import parser

os.environ['TIKA_SERVER_JAR'] = 'https://repo1.maven.org/maven2/org/apache/tika/tika-server/'+tika.__version__+'/tika-server-'+tika.__version__+'.jar'
from tika import parser

from cadmus.retrieval.search_terms_to_pmid_list import search_terms_to_pmid_list
from cadmus.pre_retrieval.pmids_to_medline_file import pmids_to_medline_file
from cadmus.pre_retrieval.creation_retrieved_df import creation_retrieved_df
from cadmus.pre_retrieval.ncbi_id_converter_batch import ncbi_id_converter_batch
from cadmus.retrieval.HTTP_setup import HTTP_setup
from cadmus.pre_retrieval.get_crossref_links_and_licenses import get_crossref_links_and_licenses
from cadmus.main.retrieval import retrieval
from cadmus.retrieval.parse_link_retrieval import parse_link_retrieval
from cadmus.pre_retrieval.check_for_retrieved_df import check_for_retrieved_df
from cadmus.retrieval.clear import clear
from cadmus.post_retrieval.content_text import content_text
from cadmus.post_retrieval.evaluation import evaluation
from cadmus.post_retrieval.correct_date_format import correct_date_format

def bioscraping(input_function, email, api_key, click_through_api_key, start = None, idx = None , full_search = None, keep_abstract = True):
    
    # first bioscraping checks whether this is an update of a previous search or a new search.
    # create all the output directories if they do not already exist
    update = check_for_retrieved_df()
    
    if update:
        print('There is already a Retrieved Dataframe, we shall add new results to this existing dataframe, excluding duplicates.')
        # load the original df to use downstream.
        original_df = pickle.load(open('./output/retrieved_df/retrieved_df2.p', 'rb'))
        # bioscraping needs to extract all the pmids where already we already have the content_text
        # these pmids will then be removed from the the search df according to the parameter used for 'full_search' 
        original_pmids = []
        drop_lines = []
        # loop through all rows checking the criteria according to 'full_search' 
        if full_search == None:
            # We are not updating the previous search(es) of the DataFrame, only looking for new lines
            print('We are not updating the previous search(es) of the DataFrame, only looking for new lines')
            original_pmids = (np.array(original_df.pmid))
        if full_search == 'light':
            # We are doing a light search, from the previous search we are only going to take a look at the missing content_text
            print('We are doing a light search, from the previous search we are only going to take a look at the missing content_text')
            for index, row in original_df.iterrows():
                # checking what is present in the content_text field from the previous search
                if row.content_text == '' or row.content_text == None or row.content_text != row.content_text or row.content_text[:4] == 'ABS:':
                    # keeping the pmid to replace the lines with the new line from this process to avoid duplicates
                    drop_lines.append(index)
                else:
                    # removing these pmids from the search
                    original_pmids.append(row['pmid'])
        if full_search == 'heavy':
            # We are doing a heavy search, trying to find new taged version from previous search
            print('We are doing a heavy search, trying to find new taged version from previous search')
            for index, row in original_df.iterrows():
                # Looking if we have at least one tagged format with a pdf format
                if (row['pdf'] == 1 and row['html'] == 1) or (row['pdf'] == 1 and row['xml'] == 1):
                    # removing these pmids from the search
                    original_pmids.append(row['pmid'])
                else:
                    # keeping the pmid to replace the lines with the new line from this process to avoid duplicates
                    drop_lines.append(index)
        
    else:
        if start != None:
            pass
        else:    
            print('This is a new project, creating all directories')
    
    # search strings and pmid lists have the same basic pipeline +/- the search at the start
    # checking the input type
    if type(input_function) == str or input_function[0].isdigit() == True:
        print('This look like a search string or list of pmids. \nIf this is not correct Please stop now')
        
        if input_function == '':
            print('You did not enter any search term')

        else:
            # run the search if the input is a string
            if type(input_function) == str:
                # This is the search step when a query string is provided resulting in a list of pmids within a dictionary
                results_d = search_terms_to_pmid_list(input_function, email, api_key)
            else:
                # the input is a list of pmids we just need to make a results_d to maintain the output variables
                
                # get todays date 
                date = datetime.datetime.today()
                date = f'{date.year}_{date.month}_{date.day}_{date.hour}_{date.minute}'
                # construct the output dict
                results_d = {'date':date, 'search_term':'', 'total_count':len(input_function), 'pmids':input_function}
                # save the output dictionary for our records of what terms used and number of records returned for a given date.
                pickle.dump(results_d, open(f'./output/esearch_results/{date}.p', 'wb'))

            # at this stage we need to see if the search is a new search or update of previous list.
            if update:
                # when this is an update we need to remove the previously used pmids from our current pipeline (the orignal df and new df will be merged at the end)
                current_pmids = results_d.get('pmids')
                # use set difference to get the new pmids only
                new_pmids = list(set(current_pmids).difference(set(original_pmids)))
                if len(new_pmids) == 0:
                    print('There are no new lines since your previous search stop the function.')
                    exit()
                else:
                    print(f'There are {len(new_pmids)} new lines since last run.')
                # set the new pmids into the results d for the next step
                results_d.update({'pmids':new_pmids}) 
            else:
                # this project is new, no need to subset the pmids
                pass

            if idx != None and start == None:
                print(f"You can't have your parameter idx not equal to None and your start = None, changing your idx to None")
                idx = None

            # starting bioscraping from somewhere else than the begining, most likely due to a previous crash of the function
            if start != None:
                try:
                    # loading the 'moving' df to restart where we stop from
                    retrieved_df = pickle.load(open(f'./output/retrieved_df/retrieved_df.p','rb'))
                    if update:
                        # subset the df to keep only the new line 
                        retrieved_df = retrieved_df[retrieved_df.pmid.isin(new_pmids)]
                except:
                    print(f"You don't have any previous retrieved_df we changed your parameters start and idx to None")
                    start = None
                    idx = None
            
            if start == None:
                # make a medline records text file for a given list of pmids
                medline_file_name = pmids_to_medline_file(results_d['date'], results_d['pmids'], email, api_key)
                # parse the medline file and create a retrieved_df with unique indexes for each record
                retrieved_df = pd.DataFrame(creation_retrieved_df(medline_file_name))
                
                # standardise the empty values and ensure there are no duplicates of pmids or dois in our retrieved_df
                retrieved_df.fillna(value=np.nan, inplace=True)
                retrieved_df = retrieved_df.drop_duplicates(keep='first', ignore_index=False, subset=['doi', 'pmid'])
                
                # use the NCBI id converter API to get any missing IDs known to the NCBI databases
                retrieved_df = ncbi_id_converter_batch(retrieved_df, email)     
                
                # we now have a retrieved_df of metadata. 
                # We can use the previous retrieved_df index to exclude ones we have looked for already.
                
                # set up the crossref metadata http request ('base')
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'base')

                #create a new column to note whether there is a crossref metadata record available - default - 0 (NO).
                retrieved_df['crossref'] = 0
                # we're going to start collection full text links now. so lets make a new column on the retrieved_df to hold a dictionary of links
                retrieved_df['full_text_links'] = [{'cr_tdm':[],'html_parse':[], 'pubmed_links':[]} for value in retrieved_df.index]
                retrieved_df['licenses'] = [{} for val in retrieved_df.index]

                # work through the retrieved_df for every available doi and query crossref for full text links
                retrieved_df = get_crossref_links_and_licenses(retrieved_df, http, base_url, headers)


                # now time to download some fulltexts, will need to create some new columns to show success or failure for each format and the actual parse dictionary

                retrieved_df['pdf'] = 0
                retrieved_df['xml'] = 0
                retrieved_df['html'] = 0
                retrieved_df['plain'] = 0
                retrieved_df['pmc_tgz'] = 0
                retrieved_df['xml_parse_d'] = [{} for index in retrieved_df.index]
                retrieved_df['html_parse_d'] = [{} for index in retrieved_df.index]
                retrieved_df['pdf_parse_d'] = [{} for index in retrieved_df.index]
                retrieved_df['plain_parse_d'] = [{} for index in retrieved_df.index]

                pickle.dump(retrieved_df, open(f'./output/retrieved_df/retrieved_df.p', 'wb'))
            else:
                pass    
            # set up the http session for crossref requests
            # http is the session object
            # base URL is empty in this case
            # headers include a clickthrough api key

            #this project is not trigered by a save
            if start == None and idx == None:
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'crossref')
                # now use the http request set up to request for each of the retrieved_df 
                retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'crossref', keep_abstract)
            #We skip all the previous step to start at the crossref step
            elif start == 'crossref' and idx == None:
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'crossref')
                # now use the http request set up to request for each of the retrieved_df 
                retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'crossref', keep_abstract)
                start = None
            #we run the code only on crossref
            elif start == 'crossref_only':
                try:
                    # we load the previous result to re-run a step
                    retrieved_df2 = pickle.load(open(f'./output/retrieved_df/retrieved_df2.p', 'rb'))
                    if update:
                        #if in update mode keep only the row we are interested in
                        retrieved_df2 = retrieved_df2[retrieved_df2.pmid.isin(new_pmids)]
                except:
                    retrieved_df2 = retrieved_df
                if idx != None:
                    try:
                        # restart from the last index it was saved at
                        divide_at = retrieved_df2.index.get_loc(idx)
                    except:
                        print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                        exit()
                    if divide_at != 0:
                        # all the row that have already been done
                        finish = retrieved_df2[divide_at:]
                        # row that have not been done yet
                        done = retrieved_df2[:divide_at]
                        http, base_url, headers = HTTP_setup(email, click_through_api_key, 'crossref')
                        # now use the http request set up to request for each of the retrieved_df 
                        finish = retrieval(finish, http, base_url, headers, 'crossref', keep_abstract, done = done)
                        retrieved_df2 = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    else:
                        http, base_url, headers = HTTP_setup(email, click_through_api_key, 'crossref')
                        # now use the http request set up to request for each of the retrieved_df 
                        retrieved_df2 = retrieval(retrieved_df2, http, base_url, headers, 'crossref', keep_abstract)

                else:
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'crossref')
                    # now use the http request set up to request for each of the retrieved_df 
                    retrieved_df2 = retrieval(retrieved_df2, http, base_url, headers, 'crossref', keep_abstract)
            # we start at the crossref step and at a specific index, could be related to a previous failled attempt
            elif start == 'crossref' and idx != None:
                try:
                    divide_at = retrieved_df.index.get_loc(idx)
                except:
                    print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                    exit()
                if divide_at != 0:
                    finish = retrieved_df[divide_at:]
                    done = retrieved_df[:divide_at]
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'crossref')
                    # now use the http request set up to request for each of the retrieved_df 
                    finish = retrieval(finish, http, base_url, headers, 'crossref', keep_abstract, done = done)
                    retrieved_df = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    #change the start and the idx to none to complete all the next step with all the row
                    start = None
                    idx = None
                else:
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'crossref')
                    # now use the http request set up to request for each of the retrieved_df 
                    retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'crossref', keep_abstract)
                    start = None
                    idx = None
            else:
                pass
            # After crossref, we are going on doi.org
            if start == None and idx == None:
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'doiorg')
                # now use the http request set up to request for each of the retrieved_df 
                retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'doiorg', keep_abstract)
            elif start == 'doiorg' and idx == None:
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'doiorg')
                # now use the http request set up to request for each of the retrieved_df 
                retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'doiorg', keep_abstract)
                start = None
            elif start == 'doiorg_only':
                try:
                    retrieved_df2 = pickle.load(open(f'./output/retrieved_df/retrieved_df2.p', 'rb'))
                    if update:
                        retrieved_df2 = retrieved_df2[retrieved_df2.pmid.isin(new_pmids)]
                except:
                    retrieved_df2 = retrieved_df
                if idx != None:
                    try:
                        divide_at = retrieved_df2.index.get_loc(idx)
                    except:
                        print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                        exit()
                    if divide_at != 0:
                        finish = retrieved_df2[divide_at:]
                        done = retrieved_df2[:divide_at]
                        http, base_url, headers = HTTP_setup(email, click_through_api_key, 'doiorg')
                        # now use the http request set up to request for each of the retrieved_df 
                        finish = retrieval(finish, http, base_url, headers, 'doiorg', keep_abstract, done = done)
                        retrieved_df2 = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    else:
                        http, base_url, headers = HTTP_setup(email, click_through_api_key, 'doiorg')
                        # now use the http request set up to request for each of the retrieved_df 
                        retrieved_df2 = retrieval(retrieved_df2, http, base_url, headers, 'doiorg', keep_abstract)

                else:
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'doiorg')
                    # now use the http request set up to request for each of the retrieved_df 
                    retrieved_df2 = retrieval(retrieved_df2, http, base_url, headers, 'doiorg', keep_abstract)
            elif start == 'doiorg' and idx != None:
                try:
                    divide_at = retrieved_df.index.get_loc(idx)
                except:
                    print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                    exit()
                if divide_at != 0:
                    finish = retrieved_df[divide_at:]
                    done = retrieved_df[:divide_at]
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'doiorg')
                    # now use the http request set up to request for each of the retrieved_df 
                    finish = retrieval(finish, http, base_url, headers, 'doiorg', keep_abstract, done = done)
                    retrieved_df = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    start = None
                    idx = None
                else:
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'doiorg')
                    # now use the http request set up to request for each of the retrieved_df 
                    retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'doiorg', keep_abstract)
                    start = None
                    idx = None
            else:
                pass
            #we continue by epmc, xml format
            if start == None and idx == None:
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'epmcxml')
                # now use the http request set up to request for each of the retrieved_df 
                retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'epmcxml', keep_abstract)
            elif start == 'epmcxml' and idx == None:
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'epmcxml')
                # now use the http request set up to request for each of the retrieved_df 
                retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'epmcxml', keep_abstract)
                start = None
            elif start == 'epmcxml_only':
                try:
                    retrieved_df2 = pickle.load(open(f'./output/retrieved_df/retrieved_df2.p', 'rb'))
                    if update:
                        retrieved_df2 = retrieved_df2[retrieved_df2.pmid.isin(new_pmids)]
                except:
                    retrieved_df2 = retrieved_df
                if idx != None:
                    try:
                        divide_at = retrieved_df2.index.get_loc(idx)
                    except:
                        print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                        exit()
                    if divide_at != 0:
                        finish = retrieved_df2[divide_at:]
                        done = retrieved_df2[:divide_at]
                        http, base_url, headers = HTTP_setup(email, click_through_api_key, 'epmcxml')
                        # now use the http request set up to request for each of the retrieved_df 
                        finish = retrieval(finish, http, base_url, headers, 'epmcxml', keep_abstract, done = done)
                        retrieved_df2 = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    else:
                        http, base_url, headers = HTTP_setup(email, click_through_api_key, 'epmcxml')
                        # now use the http request set up to request for each of the retrieved_df 
                        retrieved_df2 = retrieval(retrieved_df2, http, base_url, headers, 'epmcxml', keep_abstract)

                else:
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'epmcxml')
                    # now use the http request set up to request for each of the retrieved_df 
                    retrieved_df2 = retrieval(retrieved_df2, http, base_url, headers, 'epmcxml', keep_abstract)
            elif start == 'epmcxml' and idx != None:
                try:
                    divide_at = retrieved_df.index.get_loc(idx)
                except:
                    print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                    exit()
                if divide_at != 0:
                    finish = retrieved_df[divide_at:]
                    done = retrieved_df[:divide_at]
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'epmcxml')
                    # now use the http request set up to request for each of the retrieved_df 
                    finish = retrieval(finish, http, base_url, headers, 'epmcxml', keep_abstract, done = done)
                    retrieved_df = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    start = None
                    idx = None
                else:
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'epmcxml')
                    # now use the http request set up to request for each of the retrieved_df 
                    retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'epmcxml', keep_abstract)
                    start = None
                    idx = None
            else:
                pass  
            #pmc, xml format
            if start == None and idx == None:
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmcxmls')
                # now use the http request set up to request for each of the retrieved_df 
                retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'pmcxmls', keep_abstract)
            elif start == 'pmcxmls' and idx == None:
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmcxmls')
                # now use the http request set up to request for each of the retrieved_df 
                retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'pmcxmls', keep_abstract)
                start = None
            elif start == 'pmcxmls_only':
                try:
                    retrieved_df2 = pickle.load(open(f'./output/retrieved_df/retrieved_df2.p', 'rb'))
                    if update:
                        retrieved_df2 = retrieved_df2[retrieved_df2.pmid.isin(new_pmids)]
                except:
                    retrieved_df2 = retrieved_df
                if idx != None:
                    try:
                        divide_at = retrieved_df2.index.get_loc(idx)
                    except:
                        print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                        exit()
                    if divide_at != 0:
                        finish = retrieved_df2[divide_at:]
                        done = retrieved_df2[:divide_at]
                        http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmcxmls')
                        # now use the http request set up to request for each of the retrieved_df 
                        finish = retrieval(finish, http, base_url, headers, 'pmcxmls', keep_abstract, done = done)
                        retrieved_df2 = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    else:
                        http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmcxmls')
                        # now use the http request set up to request for each of the retrieved_df 
                        retrieved_df2 = retrieval(retrieved_df2, http, base_url, headers, 'pmcxmls', keep_abstract)

                else:
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmcxmls')
                    # now use the http request set up to request for each of the retrieved_df 
                    retrieved_df2 = retrieval(retrieved_df2, http, base_url, headers, 'pmcxmls', keep_abstract)
            elif start == 'pmcxmls' and idx != None:
                try:
                    divide_at = retrieved_df.index.get_loc(idx)
                except:
                    print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                    exit()
                if divide_at != 0:
                    finish = retrieved_df[divide_at:]
                    done = retrieved_df[:divide_at]
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmcxmls')
                    # now use the http request set up to request for each of the retrieved_df 
                    finish = retrieval(finish, http, base_url, headers, 'pmcxmls', keep_abstract, done = done)
                    retrieved_df = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    start = None
                    idx = None
                else:
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmcxmls')
                    # now use the http request set up to request for each of the retrieved_df 
                    retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'pmcxmls', keep_abstract)
                    start = None
                    idx = None
            else:
                pass
            #pmc tgz, contain pdf and xml
            if start == None and idx == None:
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmctgz')
                # now use the http request set up to request for each of the retrieved_df 
                retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'pmctgz', keep_abstract)
            elif start == 'pmctgz' and idx == None:
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmctgz')
                # now use the http request set up to request for each of the retrieved_df 
                retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'pmctgz', keep_abstract)
                start = None
            elif start == 'pmctgz_only':
                try:
                    retrieved_df2 = pickle.load(open(f'./output/retrieved_df/retrieved_df2.p', 'rb'))
                    if update:
                        retrieved_df2 = retrieved_df2[retrieved_df2.pmid.isin(new_pmids)]
                except:
                    retrieved_df2 = retrieved_df
                if idx != None:
                    try:
                        divide_at = retrieved_df2.index.get_loc(idx)
                    except:
                        print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                        exit()
                    if divide_at != 0:
                        finish = retrieved_df2[divide_at:]
                        done = retrieved_df2[:divide_at]
                        http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmctgz')
                        # now use the http request set up to request for each of the retrieved_df 
                        finish = retrieval(finish, http, base_url, headers, 'pmctgz', keep_abstract, done = done)
                        retrieved_df2 = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    else:
                        http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmctgz')
                        # now use the http request set up to request for each of the retrieved_df 
                        retrieved_df2 = retrieval(retrieved_df2, http, base_url, headers, 'pmctgz', keep_abstract)

                else:
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmctgz')
                    # now use the http request set up to request for each of the retrieved_df 
                    retrieved_df2 = retrieval(retrieved_df2, http, base_url, headers, 'pmctgz', keep_abstract)
            elif start == 'pmctgz' and idx != None:
                try:
                    divide_at = retrieved_df.index.get_loc(idx)
                except:
                    print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                    exit()
                if divide_at != 0:
                    finish = retrieved_df[divide_at:]
                    done = retrieved_df[:divide_at]
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmctgz')
                    # now use the http request set up to request for each of the retrieved_df 
                    finish = retrieval(finish, http, base_url, headers, 'pmctgz', keep_abstract, done = done)
                    retrieved_df = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    start = None
                    idx = None
                else:
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmctgz')
                    # now use the http request set up to request for each of the retrieved_df 
                    retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'pmctgz', keep_abstract)
                    start = None
                    idx = None
            else:
                pass
            #pmc, pdf format
            if start == None and idx == None:
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmcpdfs')
                # now use the http request set up to request for each of the retrieved_df 
                retrieved_df = retrieval(retrieved_df, http, base_url, '', 'pmcpdfs', keep_abstract)
            elif start == 'pmcpdfs' and idx == None:
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmcpdfs')
                # now use the http request set up to request for each of the retrieved_df 
                retrieved_df = retrieval(retrieved_df, http, base_url, '', 'pmcpdfs', keep_abstract)
                start = None
            elif start == 'pmcpdfs_only':
                try:
                    retrieved_df2 = pickle.load(open(f'./output/retrieved_df/retrieved_df2.p', 'rb'))
                    if update:
                        retrieved_df2 = retrieved_df2[retrieved_df2.pmid.isin(new_pmids)]
                except:
                    retrieved_df2 = retrieved_df
                if idx != None:
                    try:
                        divide_at = retrieved_df2.index.get_loc(idx)
                    except:
                        print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                        exit()
                    if divide_at != 0:
                        finish = retrieved_df2[divide_at:]
                        done = retrieved_df2[:divide_at]
                        http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmcpdfs')
                        # now use the http request set up to request for each of the retrieved_df 
                        finish = retrieval(finish, http, base_url, '', 'pmcpdfs', keep_abstract, done = done)
                        retrieved_df2 = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    else:
                        http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmcpdfs')
                        # now use the http request set up to request for each of the retrieved_df 
                        retrieved_df2 = retrieval(retrieved_df2, http, base_url, '', 'pmcpdfs', keep_abstract)

                else:
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmcpdfs')
                    # now use the http request set up to request for each of the retrieved_df 
                    retrieved_df2 = retrieval(retrieved_df2, http, base_url, '', 'pmcpdfs', keep_abstract)
            elif start == 'pmcpdfs' and idx != None:
                try:
                    divide_at = retrieved_df.index.get_loc(idx)
                except:
                    print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                    exit()
                if divide_at != 0:
                    finish = retrieved_df[divide_at:]
                    done = retrieved_df[:divide_at]
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmcpdfs')
                    # now use the http request set up to request for each of the retrieved_df 
                    finish = retrieval(finish, http, base_url, '', 'pmcpdfs', keep_abstract, done = done)
                    retrieved_df = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    start = None
                    idx = None
                else:
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pmcpdfs')
                    # now use the http request set up to request for each of the retrieved_df 
                    retrieved_df = retrieval(retrieved_df, http, base_url, '', 'pmcpdfs', keep_abstract)
                    start = None
                    idx = None
            else:
                pass
            # we are scraping PubMed to identify candidate link
            if start == None and idx == None:
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pubmed')
                # now use the http request set up to request for each of the retrieved_df 
                retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'pubmed', keep_abstract)
            elif start == 'pubmed' and idx == None:
                http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pubmed')
                # now use the http request set up to request for each of the retrieved_df 
                retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'pubmed', keep_abstract)
                start = None
            elif start == 'pubmed_only':
                try:
                    retrieved_df2 = pickle.load(open(f'./output/retrieved_df/retrieved_df2.p', 'rb'))
                    if update:
                        retrieved_df2 = retrieved_df2[retrieved_df2.pmid.isin(new_pmids)]
                except:
                    retrieved_df2 = retrieved_df
                if idx != None:
                    try:
                        divide_at = retrieved_df2.index.get_loc(idx)
                    except:
                        print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                        exit()
                    if divide_at != 0:
                        finish = retrieved_df2[divide_at:]
                        done = retrieved_df2[:divide_at]
                        http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pubmed')
                        # now use the http request set up to request for each of the retrieved_df 
                        finish = retrieval(finish, http, base_url, headers, 'pubmed', keep_abstract, done = done)
                        retrieved_df2 = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    else:
                        http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pubmed')
                        # now use the http request set up to request for each of the retrieved_df 
                        retrieved_df2 = retrieval(retrieved_df2, http, base_url, headers, 'pubmed', keep_abstract)

                else:
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pubmed')
                    # now use the http request set up to request for each of the retrieved_df 
                    retrieved_df2 = retrieval(retrieved_df2, http, base_url, headers, 'pubmed', keep_abstract)
            elif start == 'pubmed' and idx != None:
                try:
                    divide_at = retrieved_df.index.get_loc(idx)
                except:
                    print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                    exit()
                if divide_at != 0:
                    finish = retrieved_df[divide_at:]
                    done = retrieved_df[:divide_at]
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pubmed')
                    # now use the http request set up to request for each of the retrieved_df 
                    finish = retrieval(finish, http, base_url, headers, 'pubmed', keep_abstract, done = done)
                    retrieved_df = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    start = None
                    idx = None
                else:
                    http, base_url, headers = HTTP_setup(email, click_through_api_key, 'pubmed')
                    # now use the http request set up to request for each of the retrieved_df 
                    retrieved_df = retrieval(retrieved_df, http, base_url, headers, 'pubmed', keep_abstract)
                    start = None
                    idx = None
            else:
                pass
            #checking if the start is different than retrieved2
            if start == None:
                #select the best text candidate out of all the format available
                retrieved_df = content_text(retrieved_df)
                #changing the date format to yyyy-mm-dd
                retrieved_df = correct_date_format(retrieved_df)
                #keeping the current result before looking at the candidate links
                eval_retrieved_df = retrieved_df[['pdf', 'html', 'plain', 'xml', 'content_text']]
                #saving the retrieved df before the candidate links
                pickle.dump(retrieved_df, open(f'./output/retrieved_df/retrieved_df.p', 'wb'))
            else:
                eval_retrieved_df = retrieved_df[['pdf', 'html', 'plain', 'xml', 'content_text']]

            if start == None and idx == None:
                # updating the retreived df with the candidate links that we extracted during the previous steps
                retrieved_df2 = parse_link_retrieval(retrieved_df, email, click_through_api_key, keep_abstract)
            elif start == 'retrieved2' and idx == None:
                # restart from this step
                retrieved_df2 = parse_link_retrieval(retrieved_df, email, click_through_api_key, keep_abstract)
                start = None
            elif start == 'retrieved2_only':
                try:
                    retrieved_df2 = pickle.load(open(f'./output/retrieved_df/retrieved_df2.p', 'rb'))
                    if update:
                        retrieved_df2 = retrieved_df2[retrieved_df2.pmid.isin(new_pmids)]
                except:
                    retrieved_df2 = retrieved_df
                if idx != None:
                    try:
                        divide_at = retrieved_df2.index.get_loc(idx)
                    except:
                        print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                        exit()
                    if divide_at != 0:
                        finish = retrieved_df2[divide_at:]
                        done = retrieved_df2[:divide_at]                       
                        finish = parse_link_retrieval(finish, email, click_through_api_key, keep_abstract, done = done)
                        retrieved_df2 = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    else:
                        retrieved_df2 = parse_link_retrieval(retrieved_df2, email, click_through_api_key, keep_abstract)

                else:
                    retrieved_df2 = parse_link_retrieval(retrieved_df2, email, click_through_api_key, keep_abstract)
            elif start == 'retrieved2' and idx != None:
                try:
                    divide_at = retrieved_df.index.get_loc(idx)
                except:
                    print(f"The idx you enter was not found in the retrieved_df, please enter a correct index")
                    exit()
                if divide_at != 0:
                    finish = retrieved_df[divide_at:]
                    done = retrieved_df[:divide_at]
                    finish = parse_link_retrieval(finish, email, click_through_api_key, keep_abstract, done = done)
                    retrieved_df2 = pd.concat([done, finish], axis=0, join='outer', ignore_index=False, copy=True)
                    start = None
                    idx = None
                else:
                    retrieved_df2 = parse_link_retrieval(retrieved_df, email, click_through_api_key, keep_abstract)
                    start = None
                    idx = None
            else:
                pass
            #selecting the best new text available among all the format available
            retrieved_df2 = content_text(retrieved_df2)
            #chaging the date format to yyyy-mm-dd
            retrieved_df2 = correct_date_format(retrieved_df2)
            
            # finally if this is an update then we need to concatenate the original df and the new content df
            if update:
                original_df = original_df.drop(drop_lines)
                retrieved_df2 = pd.concat([original_df, retrieved_df2], axis=0, join='outer', ignore_index=False, copy=True)
            else:
                # no merge to perform
                pass
            
            clear()
            if start == None:
                print(f'Result for retrieved_df : ') 
                #printing the retrieval result before the candidate links
                evaluation(eval_retrieved_df)
                print('\n')
            print(f'Result for retrieved_df2 : ')
            #printing the retrieval result once all the steps have been completed
            evaluation(retrieved_df2)
            #saving the final result
            pickle.dump(retrieved_df2, open(f'./output/retrieved_df/retrieved_df2.p', 'wb'))        
    else:
        #in case the input format type is incorect
        print('Your input is not handle by the function please enter Pubmed search terms or a list of single type(dois, pmids, pmcids), without header')