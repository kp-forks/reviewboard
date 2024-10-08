import { suite } from '@beanbag/jasmine-suites';
import {
    beforeEach,
    describe,
    expect,
    it,
} from 'jasmine-core';

import {
    BaseComment,
    BaseResource,
    DiffComment,
} from 'reviewboard/common';


suite('rb/resources/models/DiffComment', function() {
    let model: DiffComment;

    beforeEach(function() {
        /* Set some sane defaults needed to pass validation. */
        model = new DiffComment({
            fileDiffID: 16,
            parentObject: new BaseResource({
                'public': true,
            }),
        });
    });

    it('getNumLines', function() {
        model.set({
            beginLineNum: 5,
            endLineNum: 10,
        });

        expect(model.getNumLines()).toBe(6);
    });

    describe('parse', function() {
        it('API payloads', function() {
            const data = model.parse({
                diff_comment: {
                    filediff: {
                        id: 1,
                        source_file: 'my-file',
                    },
                    first_line: 10,
                    id: 42,
                    interfilediff: {
                        id: 2,
                        source_file: 'my-file',
                    },
                    issue_opened: true,
                    issue_status: 'resolved',
                    num_lines: 5,
                    text: 'foo',
                    text_type: 'markdown',
                },
                stat: 'ok',
            });

            expect(data).not.toBe(undefined);
            expect(data.id).toBe(42);
            expect(data.issueOpened).toBe(true);
            expect(data.issueStatus).toBe(BaseComment.STATE_RESOLVED);
            expect(data.richText).toBe(true);
            expect(data.text).toBe('foo');
            expect(data.beginLineNum).toBe(10);
            expect(data.endLineNum).toBe(14);
            expect(data.fileDiff).not.toBe(undefined);
            expect(data.fileDiff.id).toBe(1);
            expect(data.fileDiff.get('sourceFilename')).toBe('my-file');
            expect(data.interFileDiff).not.toBe(undefined);
            expect(data.interFileDiff.id).toBe(2);
            expect(data.interFileDiff.get('sourceFilename')).toBe('my-file');
        });
    });

    describe('toJSON', function() {
        it('BaseComment.toJSON called', function() {
            spyOn(BaseComment.prototype, 'toJSON').and.callThrough();
            model.toJSON();
            expect(BaseComment.prototype.toJSON).toHaveBeenCalled();
        });

        it('first_line field', function() {
            model.set({
                beginLineNum: 100,
                endLineNum: 100,
            });

            const data = model.toJSON();
            expect(data.first_line).toBe(100);
        });

        it('num_lines field', function() {
            model.set({
                beginLineNum: 100,
                endLineNum: 105,
            });

            const data = model.toJSON();
            expect(data.num_lines).toBe(6);
        });

        describe('force_text_type field', function() {
            it('With value', function() {
                model.set('forceTextType', 'html');
                const data = model.toJSON();
                expect(data.force_text_type).toBe('html');
            });

            it('Without value', function() {
                const data = model.toJSON();
                expect(data.force_text_type).toBe(undefined);
            });
        });

        describe('include_text_types field', function() {
            it('With value', function() {
                model.set('includeTextTypes', 'html');
                const data = model.toJSON();
                expect(data.include_text_types).toBe('html');
            });

            it('Without value', function() {
                const data = model.toJSON();

                expect(data.include_text_types).toBe(undefined);
            });
        });

        describe('filediff_id field', function() {
            it('When loaded', function() {
                model.set('loaded', true);
                const data = model.toJSON();
                expect(data.filediff_id).toBe(undefined);
            });

            it('When not loaded', function() {
                const data = model.toJSON();
                expect(data.filediff_id).toBe(16);
            });
        });

        describe('interfilediff_id field', function() {
            it('When loaded', function() {
                model.set('loaded', true);
                const data = model.toJSON();
                expect(data.interfilediff_id).toBe(undefined);
            });

            it('When not loaded', function() {
                model.set('interFileDiffID', 50);
                const data = model.toJSON();
                expect(data.interfilediff_id).toBe(50);
            });

            it('When not loaded and unset', function() {
                const data = model.toJSON();
                expect(data.interfilediff_id).toBe(undefined);
            });
        });
    });

    describe('validate', function() {
        it('Inherited behavior', function() {
            spyOn(BaseComment.prototype, 'validate');
            model.validate({});
            expect(BaseComment.prototype.validate).toHaveBeenCalled();
        });

        describe('beginLineNum/endLineNum', function() {
            describe('Valid values', function() {
                it('beginLineNum == 0, endLineNum == 0', function() {
                    expect(model.validate({
                        beginLineNum: 0,
                        endLineNum: 0,
                    })).toBe(undefined);
                });

                it('beginLineNum > 0, endLineNum == beginLineNum', function() {
                    expect(model.validate({
                        beginLineNum: 10,
                        endLineNum: 10,
                    })).toBe(undefined);
                });

                it('beginLineNum > 0, endLineNum > 0', function() {
                    expect(model.validate({
                        beginLineNum: 10,
                        endLineNum: 11,
                    })).toBe(undefined);
                });
            });

            describe('Invalid values', function() {
                it('beginLineNum < 0', function() {
                    expect(model.validate({
                        beginLineNum: -1,
                    })).toBe(DiffComment.strings.BEGINLINENUM_GTE_0);
                });

                it('endLineNum < 0', function() {
                    expect(model.validate({
                        endLineNum: -1,
                    })).toBe(DiffComment.strings.ENDLINENUM_GTE_0);
                });

                it('endLineNum < beginLineNum', function() {
                    expect(model.validate({
                        beginLineNum: 20,
                        endLineNum: 10,
                    })).toBe(DiffComment.strings.BEGINLINENUM_LTE_ENDLINENUM);
                });
            });
        });

        describe('fileDiffID', function() {
            it('With value', function() {
                expect(model.validate({
                    fileDiffID: 42,
                })).toBe(undefined);
            });

            it('Unset', function() {
                expect(model.validate({
                    fileDiffID: null,
                })).toBe(DiffComment.strings.INVALID_FILEDIFF_ID);
            });
        });
    });
});
