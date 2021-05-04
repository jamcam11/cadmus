from cadmus.src.parsing import clean_soup
from cadmus.src.parsing import xml_body_p_parse
from cadmus.src.parsing import get_ab
from cadmus.src.evaluation import abstract_similarity_score
from cadmus.src.evaluation import body_unique_score
import bs4
from bs4 import BeautifulSoup
import lxml
import warnings
warnings.filterwarnings("ignore")

def xml_response_to_parse_d(retrieval_df, index, xml_response):
    parse_d = {}
    soup = BeautifulSoup(xml_response.text, 'lxml')
    # remove unwanted tags
    soup = clean_soup(soup)
    # try parse the text
    p_text = xml_body_p_parse(soup)
    # check for abstract in master_df
    if retrieval_df.loc[index, 'abstract'] != '' and retrieval_df.loc[index, 'abstract'] != None and retrieval_df.loc[index, 'abstract'] == retrieval_df.loc[index, 'abstract']:
        ab = retrieval_df.loc[index, 'abstract']
    else:    
        # try parse the abstract
        ab = get_ab(soup)
    # get the file_size
    size = len(xml_response.content)
    # get the word_count
    wc = len(p_text.split())
    
    bu_score = body_unique_score(p_text, ab)
    as_score = abstract_similarity_score(p_text, ab)
    

    # use the output from each function to build a output dictionary to use for our evaluation
    parse_d.update({'file_path':f'./output/formats/xmls/{index}.xml',
                    'text':p_text,
                    'abstract':ab,
                    'size':size,
                    'wc':wc,
                    'url':xml_response.url,
                    'body_unique_score':bu_score,
                    'ab_sim_score':as_score})
    
    if retrieval_df.loc[index, 'abstract'] == '' or retrieval_df.loc[index, 'abstract'] == None or retrieval_df.loc[index, 'abstract'] != retrieval_df.loc[index, 'abstract']:
        retrieval_df.loc[index, 'abstract'] = ab
    else:
        pass
    
    return parse_d